#!/usr/bin/env bash
set -euo pipefail

# Reusable raw CV + raw JD extraction → review → role authoring → PREVIEW gap run.
# The script stores only prettified JSON in the results directory. Temporary raw
# HTTP bodies are kept outside the result directory and removed on exit.

BASE_URL="${PAI_API_BASE_URL:-http://localhost:8000}"
CV_PATH="${PAI_CV_PATH:-}"
JD_PATH="${PAI_JD_PATH:-}"
RESULTS_ROOT="${PAI_RESULTS_DIR:-/Users/mac/Developers/work/PAI Learning/test/results}"
RUN_ID="${PAI_RUN_ID:-$(date +%Y%m%d-%H%M%S)}"
EXPECTED_CV_SHA256="${PAI_CV_SHA256:-}"
EXPECTED_JD_SHA256="${PAI_JD_SHA256:-}"
POLL_ATTEMPTS="${PAI_POLL_ATTEMPTS:-180}"
POLL_DELAY_SECONDS="${PAI_POLL_DELAY_SECONDS:-2}"
LEARNER_ID="${PAI_LEARNER_ID:-00000000-0000-0000-0000-000000000005}"
REVIEWER_ID="${PAI_REVIEWER_ID:-00000000-0000-0000-0000-000000000004}"
POLICY_ID="${PAI_POLICY_ID:-cv-jd-gap-${RUN_ID//[^A-Za-z0-9._:-]/-}}"
POLICY_VERSION="${PAI_POLICY_VERSION:-1}"
PACK_ID="${PAI_PACK_ID:-it_ai}"
PACK_VERSION="${PAI_PACK_VERSION:-1}"
PACK_CHECKSUM="${PAI_PACK_CHECKSUM:-sha256:it-ai-v1}"

if [[ -z "$CV_PATH" || -z "$JD_PATH" ]]; then
  echo "Set PAI_CV_PATH and PAI_JD_PATH before running." >&2
  exit 2
fi
if [[ ! -f "$CV_PATH" || ! -f "$JD_PATH" ]]; then
  echo "CV/JD path is not a file." >&2
  exit 2
fi
if [[ "${CV_PATH##*.}" != "pdf" && "${CV_PATH##*.}" != "PDF" ]]; then
  echo "CV must be PDF." >&2
  exit 2
fi
if [[ "${JD_PATH##*.}" != "docx" && "${JD_PATH##*.}" != "DOCX" ]]; then
  echo "JD must be DOCX." >&2
  exit 2
fi

mkdir -p "$RESULTS_ROOT"
RUN_DIR="$RESULTS_ROOT/$RUN_ID"
mkdir -p "$RUN_DIR"
TMP_DIR="$(mktemp -d "${TMPDIR:-/tmp}/pai-cv-jd-gap.XXXXXX")"
trap 'rm -rf "$TMP_DIR"' EXIT

pretty_json() {
  local source="$1"
  local destination="$2"
  python3 - "$source" "$destination" <<'PY'
import json
import sys

source, destination = sys.argv[1:]
with open(source, encoding="utf-8") as handle:
    value = json.load(handle)
with open(destination, "w", encoding="utf-8") as handle:
    json.dump(value, handle, ensure_ascii=False, indent=2, sort_keys=True)
    handle.write("\n")
PY
}

json_value() {
  local source="$1"
  local path="$2"
  python3 - "$source" "$path" <<'PY'
import json
import sys

value = json.load(open(sys.argv[1], encoding="utf-8"))
for key in sys.argv[2].split("."):
    value = value[key]
if isinstance(value, (dict, list)):
    print(json.dumps(value, ensure_ascii=False, separators=(",", ":")))
else:
    print(value)
PY
}

request() {
  local method="$1"
  local url="$2"
  local destination="$3"
  shift 3
  local raw="$TMP_DIR/response.json"
  local code
  code="$(curl -sS --connect-timeout 10 --max-time 180 -o "$raw" -w '%{http_code}' \
    -X "$method" "$url" "$@")"
  pretty_json "$raw" "$destination"
  if [[ "$code" -lt 200 || "$code" -ge 300 ]]; then
    echo "HTTP $code $method $url; see $destination" >&2
    return 1
  fi
}

sha256_file() {
  shasum -a 256 "$1" | awk '{print $1}'
}

check_hash() {
  local label="$1"
  local path="$2"
  local expected="$3"
  local actual
  actual="$(sha256_file "$path")"
  if [[ -n "$expected" && "$actual" != "$expected" ]]; then
    echo "$label SHA-256 mismatch: expected $expected, got $actual" >&2
    exit 3
  fi
  printf '%s\n' "$actual"
}

json_payload_from_file_kind() {
  python3 - "$1" "$2" <<'PY'
import json
import sys
print(json.dumps({"document_id": sys.argv[1], "document_kind": sys.argv[2]}))
PY
}

poll_job() {
  local kind="$1"
  local job_id="$2"
  local destination="$3"
  local status=""
  for attempt in $(seq 1 "$POLL_ATTEMPTS"); do
    request GET "$BASE_URL/extraction-jobs/$job_id" "$destination" \
      -H "X-PAI-Actor-ID: $LEARNER_ID"
    status="$(json_value "$destination" status)"
    printf '%s extraction status: %s (%s/%s)\n' "$kind" "$status" "$attempt" "$POLL_ATTEMPTS"
    if [[ "$status" == "succeeded" ]]; then
      return 0
    fi
    if [[ "$status" == "failed" ]]; then
      echo "$kind extraction failed; see $destination" >&2
      return 1
    fi
    sleep "$POLL_DELAY_SECONDS"
  done
  echo "$kind extraction timed out; see $destination" >&2
  return 1
}

upload_and_accept() {
  local kind="$1"
  local path="$2"
  local stem="$3"
  local content_type="$4"
  local document_file="$RUN_DIR/${stem}-upload.json"
  local job_file="$RUN_DIR/${stem}-job.json"
  local profile_file="$RUN_DIR/${stem}-extraction-profile.json"
  local accepted_file="$RUN_DIR/${stem}-accepted-profile.json"
  local document_id job_id profile_id version payload

  request POST "$BASE_URL/documents" "$document_file" \
    -H "X-PAI-Actor-ID: $LEARNER_ID" \
    -F "document_kind=$kind" \
    -F "file=@$path;type=$content_type"
  [[ "$(json_value "$document_file" status)" == "clean" ]]
  document_id="$(json_value "$document_file" id)"

  payload="$(json_payload_from_file_kind "$document_id" "$kind")"
  request POST "$BASE_URL/extraction-jobs" "$job_file" \
    -H "X-PAI-Actor-ID: $LEARNER_ID" \
    -H 'Content-Type: application/json' \
    --data "$payload"
  job_id="$(json_value "$job_file" id)"

  poll_job "$kind" "$job_id" "$job_file"
  profile_id="$(json_value "$job_file" profile_id)"
  request GET "$BASE_URL/extraction-profiles/$profile_id" "$profile_file" \
    -H "X-PAI-Actor-ID: $LEARNER_ID"
  version="$(json_value "$profile_file" version)"
  payload="$(python3 - "$version" <<'PY'
import json
import sys
print(json.dumps({"expected_version": int(sys.argv[1])}))
PY
)"
  request POST "$BASE_URL/extraction-profiles/$profile_id/accept" "$accepted_file" \
    -H "X-PAI-Actor-ID: $REVIEWER_ID" \
    -H 'Content-Type: application/json' \
    --data "$payload"
  [[ "$(json_value "$accepted_file" review_state)" == "accepted" ]]

}

echo "Checking input hashes..."
CV_SHA256="$(check_hash CV "$CV_PATH" "$EXPECTED_CV_SHA256")"
JD_SHA256="$(check_hash JD "$JD_PATH" "$EXPECTED_JD_SHA256")"

request GET "$BASE_URL/health/ready" "$RUN_DIR/health-ready.json"

upload_and_accept cv "$CV_PATH" cv application/pdf
upload_and_accept jd "$JD_PATH" jd \
  application/vnd.openxmlformats-officedocument.wordprocessingml.document

CV_PROFILE_ID="$(json_value "$RUN_DIR/cv-accepted-profile.json" id)"
JD_PROFILE_ID="$(json_value "$RUN_DIR/jd-accepted-profile.json" id)"

draft_payload="$(python3 - "$JD_PROFILE_ID" "$RUN_ID" <<'PY'
import json
import sys
print(json.dumps({"source_jd_profile_id": sys.argv[1], "correlation_id": f"jd-draft-{sys.argv[2]}"}))
PY
)"
request POST "$BASE_URL/role-profile-drafts?include_requirement_findings=true" \
  "$RUN_DIR/jd-role-profile-draft.json" \
  -H "X-PAI-Actor-ID: $REVIEWER_ID" \
  -H 'Content-Type: application/json' \
  --data "$draft_payload"
DRAFT_ID="$(json_value "$RUN_DIR/jd-role-profile-draft.json" id)"
DRAFT_VERSION="$(json_value "$RUN_DIR/jd-role-profile-draft.json" version)"

author_payload="$(python3 - "$RUN_DIR/jd-role-profile-draft.json" "$DRAFT_VERSION" <<'PY'
import json
import sys
draft = json.load(open(sys.argv[1], encoding="utf-8"))
print(json.dumps({
    "expected_version": int(sys.argv[2]),
    "title": "AI Engineer - extracted role",
    "requirements": draft["requirements"],
}))
PY
)"
request PATCH "$BASE_URL/role-profile-drafts/$DRAFT_ID?include_requirement_findings=true" \
  "$RUN_DIR/jd-role-profile-authored.json" \
  -H "X-PAI-Actor-ID: $REVIEWER_ID" \
  -H 'Content-Type: application/json' \
  --data "$author_payload"
AUTHORED_VERSION="$(json_value "$RUN_DIR/jd-role-profile-authored.json" version)"

validate_payload="$(python3 - "$AUTHORED_VERSION" <<'PY'
import json
import sys
print(json.dumps({"expected_version": int(sys.argv[1])}))
PY
)"
request POST "$BASE_URL/role-profile-drafts/$DRAFT_ID/validate?include_requirement_findings=true" \
  "$RUN_DIR/jd-role-profile-validated.json" \
  -H "X-PAI-Actor-ID: $REVIEWER_ID" \
  -H 'Content-Type: application/json' \
  --data "$validate_payload"
VALIDATED_VERSION="$(json_value "$RUN_DIR/jd-role-profile-validated.json" version)"

policy_payload="$(python3 - "$POLICY_ID" "$POLICY_VERSION" "$PACK_ID" "$PACK_VERSION" "$PACK_CHECKSUM" <<'PY'
import json
import sys
print(json.dumps({
    "policy_id": sys.argv[1],
    "version": sys.argv[2],
    "domain_pack_id": sys.argv[3],
    "domain_pack_version": sys.argv[4],
    "domain_pack_checksum": sys.argv[5],
    "description": "Reusable CV-JD capability preview policy",
}))
PY
)"
request POST "$BASE_URL/semantic-policies" "$RUN_DIR/semantic-policy-created.json" \
  -H "X-PAI-Actor-ID: $REVIEWER_ID" \
  -H 'Content-Type: application/json' \
  --data "$policy_payload"
request POST "$BASE_URL/semantic-policies/$POLICY_ID/versions/$POLICY_VERSION/activate" \
  "$RUN_DIR/semantic-policy-activated.json" \
  -H "X-PAI-Actor-ID: $REVIEWER_ID"

approve_payload="$(python3 - "$VALIDATED_VERSION" "$POLICY_ID" "$POLICY_VERSION" "$PACK_ID" "$PACK_VERSION" <<'PY'
import json
import sys
print(json.dumps({
    "expected_version": int(sys.argv[1]),
    "requested_status": "provisional",
    "semantic_policy_ref": {"policy_id": sys.argv[2], "policy_version": sys.argv[3]},
    "semantic_policy": {
        "core_version": "semantic-core-v1",
        "pack_refs": [{"pack_id": sys.argv[4], "version": sys.argv[5]}],
    },
}))
PY
)"
request POST "$BASE_URL/role-profile-drafts/$DRAFT_ID/approve?include_requirement_findings=true" \
  "$RUN_DIR/role-profile-approved.json" \
  -H "X-PAI-Actor-ID: $REVIEWER_ID" \
  -H 'Content-Type: application/json' \
  --data "$approve_payload"
ROLE_PROFILE_ID="$(json_value "$RUN_DIR/role-profile-approved.json" approved_role_profile_id)"

analysis_payload="$(python3 - "$CV_PROFILE_ID" "$ROLE_PROFILE_ID" "$RUN_ID" <<'PY'
import json
import sys
print(json.dumps({
    "cv_profile_id": sys.argv[1],
    "current_target_profile_id": sys.argv[2],
    "correlation_id": f"capability-gap-{sys.argv[3]}",
}))
PY
)"
request POST "$BASE_URL/capability-gap-portfolios" "$RUN_DIR/capability-gap-analysis.json" \
  -H "X-PAI-Actor-ID: $LEARNER_ID" \
  -H 'Content-Type: application/json' \
  --data "$analysis_payload"
PORTFOLIO_ID="$(json_value "$RUN_DIR/capability-gap-analysis.json" id)"
request GET "$BASE_URL/capability-gap-portfolios/$PORTFOLIO_ID" \
  "$RUN_DIR/capability-gap-portfolio-get.json" \
  -H "X-PAI-Actor-ID: $LEARNER_ID"

python3 - "$RUN_DIR/capability-gap-analysis.json" "$POLICY_ID" "$POLICY_VERSION" "$PACK_ID" "$PACK_VERSION" "$PACK_CHECKSUM" <<'PY'
import json
import sys
path, policy_id, policy_version, pack_id, pack_version, checksum = sys.argv[1:]
portfolio = json.load(open(path, encoding="utf-8"))
assert portfolio["current_role"]["usage_mode"] == "preview"
assert portfolio["preview_readiness"]["analysis_mode"] == "preview"
assert portfolio["preview_readiness"]["final_competency_decision_prohibited"] is True
snapshot = portfolio["semantic_policies"][0]
assert snapshot["policy_id"] == policy_id
assert snapshot["policy_version"] == policy_version
assert snapshot["pack_refs"] == [{"pack_id": pack_id, "version": pack_version}]
assert snapshot["pack_checksum"] == checksum
assert "combined_score" not in portfolio
assert "readiness_score" not in portfolio
PY

manifest_payload="$(python3 - "$RUN_ID" "$CV_PATH" "$JD_PATH" "$CV_SHA256" "$JD_SHA256" "$CV_PROFILE_ID" "$JD_PROFILE_ID" "$DRAFT_ID" "$ROLE_PROFILE_ID" "$PORTFOLIO_ID" "$POLICY_ID" "$POLICY_VERSION" "$PACK_ID" "$PACK_VERSION" "$PACK_CHECKSUM" <<'PY'
import json
import sys
keys = (
    "run_id", "cv_path", "jd_path", "cv_sha256", "jd_sha256", "cv_profile_id",
    "jd_profile_id", "draft_id", "role_profile_id", "portfolio_id", "policy_id",
    "policy_version", "pack_id", "pack_version", "pack_checksum",
)
print(json.dumps(dict(zip(keys, sys.argv[1:], strict=True))))
PY
)"
printf '%s\n' "$manifest_payload" > "$TMP_DIR/manifest.json"
pretty_json "$TMP_DIR/manifest.json" "$RUN_DIR/run-manifest.json"

echo "Capability Gap Analysis completed."
echo "Results: $RUN_DIR"
echo "CV profile: $CV_PROFILE_ID"
echo "JD profile: $JD_PROFILE_ID"
echo "Role profile: $ROLE_PROFILE_ID"
echo "Portfolio: $PORTFOLIO_ID"
