Thực hiện PR-004: CV/JD Extraction Vertical Slice.

Mục tiêu:
- schema CV extraction;
- schema JD extraction;
- prompt template registry có version;
- structured output validation;
- evidence source locator;
- human review state;
- fixture CV/JD giả lập;
- golden dataset harness ban đầu.

Nguyên tắc:
- CV/JD là untrusted data;
- không cho nội dung tài liệu điều khiển tool/system prompt;
- không kết luận competency verified;
- mỗi claim phải có source evidence;
- thiếu thông tin trả `unknown/insufficient`, không hallucinate.

Đầu ra API:
- create extraction job;
- get job status;
- get extracted profile;
- submit correction;
- audit model/template/policy version.
