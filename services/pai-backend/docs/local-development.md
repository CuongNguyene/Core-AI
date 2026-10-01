# Chạy PAI local độc lập

Tài liệu này chạy PAI từ chính repository `pai-backend`. Nó không dùng Docker
Compose, database hoặc source code của BrainHub/LMS cũ.

## Chuẩn bị

```bash
cd ~/workspace/pai-backend
cp backend/.env.example backend/.env
cp devops/compose/.env.example devops/compose/.env
```

`backend/.env.example` và `backend/.env` dùng cùng một bộ tên biến; file
example chỉ chứa placeholder, còn `.env` là cấu hình local và đã bị Git ignore.
Không commit API key,
JWT signing key, mật khẩu database, mật khẩu Redis/MinIO hoặc actor private key.

Để FastAPI chạy được, thay các placeholder bắt buộc trong `backend/.env` bằng
giá trị local hợp lệ, đặc biệt `JWT_SIGNING_KEY`,
`PAI_BOOTSTRAP_ADMIN_PASSWORD`, `PAI_INTEGRATION_API_KEY` và
`ACTOR_CONTEXT_PUBLIC_KEYS_JSON`.

## Khởi động

```bash
docker compose \
  --env-file devops/compose/.env \
  -f devops/compose/docker-compose.local.yml \
  up -d --build
```

Compose tạo một project `pai-local` với PostgreSQL, Redis, MinIO, ClamAV, API,
extraction worker và course-generation worker. API entrypoint tự chạy Alembic
migration trước khi mở FastAPI.

Mặc định host ports là:

| Service | URL/port |
| --- | --- |
| PAI API | `http://127.0.0.1:18000` |
| PAI readiness | `http://127.0.0.1:18000/health/ready` |
| PostgreSQL (DBeaver) | `127.0.0.1:15433`, database/user `pai` |
| Redis | `127.0.0.1:16379` |
| MinIO API | `http://127.0.0.1:19000` |
| MinIO Console | `http://127.0.0.1:19001` |

Mật khẩu PostgreSQL cho DBeaver là `POSTGRES_PASSWORD` trong
`devops/compose/.env`.

Các port mặc định cố ý khác BrainHub để hai stack có thể cùng tồn tại. Muốn dùng
port khác, chỉ sửa `devops/compose/.env`, không sửa Compose file.

## Bootstrap actor cho Frappe local

Core-AI giữ actor public key trong `backend/.env`; private key không được đưa
vào PAI hoặc Git. Chạy command sau từ `services/pai-backend`:

```bash
cd backend
uv run python scripts/bootstrap_dev_actor.py
```

Command dùng organization/actor fixture local ổn định, ghi public key vào
`backend/.env`, và ghi raw Ed25519 private key dạng base64url vào
`.local-secrets/frappe-lms-local/actor_ed25519.key` với mode `0600`.

Chạy lại command sẽ reuse key hiện tại. Nếu private key và public key đã đăng
ký không khớp, command fail-closed; không tự rotate key.

## Kiểm tra và dừng

```bash
docker compose --env-file devops/compose/.env -f devops/compose/docker-compose.local.yml ps
curl http://127.0.0.1:18000/health/ready
docker compose --env-file devops/compose/.env -f devops/compose/docker-compose.local.yml logs -f backend
docker compose --env-file devops/compose/.env -f devops/compose/docker-compose.local.yml down
```

`down` chỉ dừng stack `pai-local`; không dừng BrainHub. Không chạy `down -v` trừ
khi chủ động xóa toàn bộ dữ liệu local PAI.

## Kết nối Frappe LMS local

Trong PAI Settings của site Frappe local, dùng `http://127.0.0.1:18000` cho
PAI Service URL. Tùy chọn HTTP loopback chỉ được chấp nhận khi Frappe chạy
developer mode; môi trường ngoài local phải dùng HTTPS.
