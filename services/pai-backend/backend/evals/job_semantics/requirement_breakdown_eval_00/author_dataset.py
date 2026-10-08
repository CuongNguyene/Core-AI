"""Reproducibly render the hand-authored synthetic posting rows to JSONL."""

from __future__ import annotations

import html
import json
from pathlib import Path

ROOT = Path(__file__).parent

# Each row is an original fictional role and its own authored clauses. The
# renderer only assigns stable IDs, wraps exact text in HTML, and writes JSONL.
ROWS = [
    (
        "FINANCE_ACCOUNTING",
        "VIETNAMESE",
        "Chuyên viên công nợ",
        "Đối chiếu công nợ khách hàng theo từng kỳ.",
        "Phân tích khoản chậm thanh toán để đề xuất hướng xử lý.",
        "Lưu biên bản đối chiếu vào hồ sơ tháng.",
        "Có ít nhất 2 năm theo dõi công nợ doanh nghiệp.",
        "Tốt nghiệp cao đẳng hoặc đại học ngành kế toán.",
        "Ưu tiên ứng viên có chứng chỉ kế toán viên.",
        "Trao đổi rõ ràng với khách hàng khi số liệu chênh lệch.",
        "Làm việc tại văn phòng, giờ hành chính.",
    ),
    (
        "FINANCE_ACCOUNTING",
        "VIETNAMESE",
        "Kế toán thanh toán",
        "Kiểm tra chứng từ trước khi lập lệnh chi.",
        "Theo dõi lịch thanh toán và xử lý khoản đến hạn.",
        "Sắp xếp chứng từ theo mã giao dịch.",
        "Tối thiểu 3 năm làm kế toán thanh toán.",
        "Có bằng đại học kế toán hoặc tài chính.",
        "Chứng chỉ kế toán quốc tế là lợi thế.",
        "Cẩn thận khi kiểm tra số tài khoản và số tiền.",
        "Mức lương trao đổi theo kinh nghiệm.",
    ),
    (
        "FINANCE_ACCOUNTING",
        "VIETNAMESE",
        "Chuyên viên lập ngân sách",
        "Tổng hợp dữ liệu chi phí từ các phòng ban.",
        "Xây dựng dự báo ngân sách quý và giải thích biến động.",
        "Gửi lịch họp rà soát ngân sách trước phiên họp.",
        "Có kinh nghiệm lập ngân sách tối thiểu 2 năm.",
        "Tốt nghiệp ngành tài chính, kế toán hoặc kinh tế.",
        "Ưu tiên chứng chỉ CFA cấp độ phù hợp.",
        "Trình bày giả định tài chính có căn cứ.",
        "Có thể tham gia họp cuối tháng.",
    ),
    (
        "FINANCE_ACCOUNTING",
        "VIETNAMESE",
        "Kiểm soát nội bộ",
        "Thực hiện kiểm tra mẫu các giao dịch mua hàng.",
        "Ghi nhận phát hiện và theo dõi kế hoạch khắc phục.",
        "Cập nhật trạng thái phát hiện trên sổ theo dõi.",
        "Từng làm kiểm soát hoặc kiểm toán nội bộ từ 3 năm.",
        "Bằng đại học về kiểm toán hoặc ngành liên quan.",
        "Chứng chỉ CIA được ưu tiên.",
        "Giữ thái độ khách quan khi trao đổi phát hiện.",
        "Thỉnh thoảng đi công tác trong nước.",
    ),
    (
        "FINANCE_ACCOUNTING",
        "VIETNAMESE",
        "Chuyên viên thuế",
        "Chuẩn bị bảng kê hóa đơn đầu vào và đầu ra.",
        "Đối chiếu nghĩa vụ thuế với sổ cái trước hạn nộp.",
        "Lưu bản xác nhận nộp hồ sơ thuế.",
        "Ít nhất 2 năm xử lý hồ sơ thuế doanh nghiệp.",
        "Tốt nghiệp đại học chuyên ngành kế toán hoặc luật kinh tế.",
        "Có chứng chỉ hành nghề dịch vụ thuế là lợi thế.",
        "Diễn giải thay đổi quy định bằng ngôn ngữ dễ hiểu.",
        "Địa điểm làm việc tại Đà Nẵng.",
    ),
    (
        "FINANCE_ACCOUNTING",
        "VIETNAMESE",
        "Chuyên viên phân tích tín dụng",
        "Thẩm định hồ sơ tài chính của khách hàng doanh nghiệp.",
        "Xây dựng dòng tiền cơ sở và phân tích khả năng trả nợ.",
        "Hoàn thành biểu mẫu thẩm định theo checklist.",
        "Có 3 năm phân tích tín dụng hoặc tài chính doanh nghiệp.",
        "Bằng cử nhân tài chính, ngân hàng hoặc kinh tế.",
        "Ưu tiên chứng chỉ phân tích tài chính CFA.",
        "Tóm tắt rủi ro tín dụng cân bằng, không bỏ sót giả định.",
        "Có thể làm theo ca luân phiên.",
    ),
    (
        "FINANCE_ACCOUNTING",
        "ENGLISH",
        "Treasury Operations Analyst",
        "Reconcile daily bank balances across operating accounts.",
        "Prepare a short-term liquidity forecast for the treasury lead.",
        "Archive approved bank statements by closing date.",
        "At least two years of corporate treasury operations experience.",
        "A bachelor's degree in finance, accounting, or economics.",
        "An ACT qualification is preferred but not mandatory.",
        "Explain cash movements clearly to non-finance partners.",
        "The role is based at the regional office.",
    ),
    (
        "FINANCE_ACCOUNTING",
        "ENGLISH",
        "Revenue Assurance Specialist",
        "Compare billed transactions with service activation records.",
        "Investigate recurring revenue variances and document causes.",
        "Submit the weekly exception log before the review meeting.",
        "Three years of revenue assurance or billing analysis experience.",
        "A degree in accounting, finance, or a related subject.",
        "CPA certification is an advantage.",
        "Good professional skills are required.",
        "Benefits are described during the interview.",
    ),
    (
        "SOFTWARE_ENGINEERING",
        "VIETNAMESE",
        "Kỹ sư backend",
        "Thiết kế endpoint REST cho luồng đặt lịch.",
        "Tối ưu truy vấn để giảm thời gian phản hồi API.",
        "Cập nhật hướng dẫn chạy dịch vụ trong README.",
        "Có ít nhất 3 năm phát triển dịch vụ Python.",
        "Tốt nghiệp đại học công nghệ thông tin hoặc tương đương.",
        "Ưu tiên chứng chỉ cloud associate.",
        "Tiếp nhận phản biện trong code review với thái độ xây dựng.",
        "Làm việc kết hợp tại văn phòng và từ xa.",
    ),
    (
        "SOFTWARE_ENGINEERING",
        "VIETNAMESE",
        "Kỹ sư frontend",
        "Xây dựng màn hình quản lý đơn hàng bằng Vue.",
        "Tích hợp giao diện với API và xử lý trạng thái lỗi.",
        "Gắn nhãn phiên bản cho bản build nghiệm thu.",
        "Tối thiểu 2 năm phát triển giao diện web.",
        "Có bằng đại học kỹ thuật hoặc lĩnh vực liên quan.",
        "Chứng chỉ accessibility là một lợi thế.",
        "Giải thích trade-off giao diện cho nhóm sản phẩm.",
        "Thời gian làm việc linh hoạt theo nhóm.",
    ),
    (
        "SOFTWARE_ENGINEERING",
        "VIETNAMESE",
        "Kỹ sư nền tảng",
        "Duy trì pipeline build và kiểm tra artifact.",
        "Thiết kế cảnh báo cho dịch vụ có lưu lượng cao.",
        "Luân phiên trực theo lịch đã thống nhất.",
        "Có kinh nghiệm vận hành hệ thống Linux từ 4 năm.",
        "Tốt nghiệp ngành khoa học máy tính hoặc hệ thống thông tin.",
        "Ưu tiên chứng chỉ Kubernetes administrator.",
        "Ứng phó sự cố bình tĩnh và ghi lại quyết định.",
        "Có lịch trực ngoài giờ theo phiên.",
    ),
    (
        "SOFTWARE_ENGINEERING",
        "VIETNAMESE",
        "Kỹ sư kiểm thử tự động",
        "Viết kiểm thử API cho các luồng thanh toán chính.",
        "Phân tích flaky test và đề xuất cách ổn định suite.",
        "Đính kèm log kiểm thử vào ticket lỗi.",
        "Từ 2 năm làm kiểm thử phần mềm tự động.",
        "Bằng cao đẳng hoặc đại học ngành CNTT.",
        "ISTQB Foundation là chứng chỉ được ưu tiên.",
        "Mô tả lỗi bằng bước tái hiện ngắn gọn.",
        "Có thể bắt đầu trong tháng tới.",
    ),
    (
        "SOFTWARE_ENGINEERING",
        "VIETNAMESE",
        "Kỹ sư ứng dụng di động",
        "Phát triển luồng đăng nhập cho ứng dụng Android.",
        "Đo mức tiêu thụ bộ nhớ trên thiết bị cấu hình thấp.",
        "Chuẩn bị ghi chú phát hành cho mỗi phiên bản.",
        "Có ít nhất 3 năm phát triển ứng dụng di động.",
        "Tốt nghiệp ngành phần mềm hoặc điện tử viễn thông.",
        "Ưu tiên chứng chỉ Android developer.",
        "Phối hợp chủ động với thiết kế khi đặc tả chưa rõ.",
        "Địa điểm làm việc tại Thành phố Hồ Chí Minh.",
    ),
    (
        "SOFTWARE_ENGINEERING",
        "VIETNAMESE",
        "Kỹ sư bảo mật ứng dụng",
        "Rà soát luồng xác thực trong các dịch vụ nội bộ.",
        "Tái hiện và ưu tiên lỗ hổng theo mức độ ảnh hưởng.",
        "Gửi báo cáo kiểm tra theo mẫu của nhóm.",
        "Có kinh nghiệm bảo mật ứng dụng web từ 3 năm.",
        "Bằng đại học công nghệ thông tin hoặc an toàn thông tin.",
        "Chứng chỉ OSCP được xem là lợi thế.",
        "Trình bày rủi ro kỹ thuật với nhóm không chuyên.",
        "Mức lương cạnh tranh theo năng lực.",
    ),
    (
        "SOFTWARE_ENGINEERING",
        "ENGLISH",
        "Data Platform Engineer",
        "Build reliable ingestion jobs for product event streams.",
        "Tune partitioning and retention for analytical storage.",
        "Update the on-call handover note after each rotation.",
        "Four years working with distributed data platforms.",
        "A computer science or engineering degree is required.",
        "A cloud data engineering certificate is desirable.",
        "Communicate platform design trade-offs clearly across engineering teams.",
        "Occasional weekend support is scheduled in advance.",
    ),
    (
        "SOFTWARE_ENGINEERING",
        "ENGLISH",
        "Application Support Developer",
        "Trace production errors from request logs to service code.",
        "Deliver small fixes with regression coverage.",
        "Record each resolved incident in the support register.",
        "Two years supporting a production software product.",
        "A degree in software engineering or equivalent study.",
        "A service management certificate is preferred.",
        "Strong overall aptitude required.",
        "The position follows a rotating support schedule.",
    ),
    (
        "DATA_ANALYTICS",
        "VIETNAMESE",
        "Chuyên viên phân tích dữ liệu",
        "Làm sạch dữ liệu giao dịch trước khi lập báo cáo.",
        "Xây dựng dashboard theo dõi tỷ lệ chuyển đổi.",
        "Lưu truy vấn SQL đã chạy vào thư mục dự án.",
        "Có ít nhất 2 năm phân tích dữ liệu kinh doanh.",
        "Tốt nghiệp đại học thống kê, toán hoặc hệ thống thông tin.",
        "Ưu tiên chứng chỉ phân tích dữ liệu.",
        "Giải thích kết quả bằng biểu đồ và giả định rõ ràng.",
        "Có thể trao đổi về mức lương khi phỏng vấn.",
    ),
    (
        "DATA_ANALYTICS",
        "VIETNAMESE",
        "Chuyên viên phân tích vận hành",
        "Đo thời gian xử lý hồ sơ tại từng công đoạn.",
        "Phân tích nguyên nhân khiến hàng đợi tăng đột biến.",
        "Cập nhật bảng theo dõi SLA mỗi tuần.",
        "Tối thiểu 2 năm làm phân tích vận hành.",
        "Bằng đại học về kinh tế lượng hoặc quản trị vận hành.",
        "Chứng chỉ Lean Six Sigma là lợi thế.",
        "Hỏi lại giả định trước khi kết luận từ dữ liệu.",
        "Làm việc tại văn phòng Hà Nội.",
    ),
    (
        "DATA_ANALYTICS",
        "VIETNAMESE",
        "Kỹ sư phân tích dữ liệu",
        "Thiết kế mô hình dữ liệu cho báo cáo doanh thu.",
        "Kiểm tra chất lượng dữ liệu sau mỗi lần nạp.",
        "Ghi phiên bản schema trong tài liệu nhóm.",
        "Có kinh nghiệm SQL và mô hình dữ liệu từ 3 năm.",
        "Tốt nghiệp khoa học dữ liệu hoặc ngành kỹ thuật liên quan.",
        "Ưu tiên chứng chỉ dbt fundamentals.",
        "Phối hợp với người dùng để xác định định nghĩa chỉ số.",
        "Có thể làm việc từ xa hai ngày mỗi tuần.",
    ),
    (
        "DATA_ANALYTICS",
        "VIETNAMESE",
        "Chuyên viên phân tích rủi ro",
        "Tổng hợp tín hiệu rủi ro từ dữ liệu giao dịch.",
        "Kiểm định ngưỡng cảnh báo trên dữ liệu lịch sử.",
        "Nộp bảng kiểm định theo chu kỳ tháng.",
        "Ít nhất 3 năm phân tích rủi ro định lượng.",
        "Bằng đại học toán ứng dụng, thống kê hoặc tài chính.",
        "CFA hoặc FRM là chứng chỉ được ưu tiên.",
        "Trình bày giới hạn dữ liệu trung thực.",
        "Có thể công tác ngắn ngày theo kế hoạch.",
    ),
    (
        "DATA_ANALYTICS",
        "VIETNAMESE",
        "Chuyên viên báo cáo",
        "Tự động hóa báo cáo tồn kho bằng bảng điều khiển.",
        "Đối chiếu số liệu báo cáo với nguồn vận hành.",
        "Gửi bản PDF báo cáo trước ngày làm việc thứ ba.",
        "Có 2 năm xây dựng báo cáo quản trị.",
        "Tốt nghiệp đại học kế toán, kinh tế hoặc dữ liệu.",
        "Chứng chỉ Power BI được đánh giá cao.",
        "Lắng nghe yêu cầu và xác nhận phạm vi báo cáo.",
        "Lịch nghỉ theo chính sách công ty.",
    ),
    (
        "DATA_ANALYTICS",
        "VIETNAMESE",
        "Nhà phân tích sản phẩm",
        "Phân tích funnel kích hoạt người dùng mới.",
        "Thiết kế nhóm đối chứng cho thử nghiệm tính năng.",
        "Đăng kết quả thử nghiệm vào wiki nội bộ.",
        "Tối thiểu 2 năm phân tích sản phẩm số.",
        "Bằng đại học ngành định lượng hoặc kinh doanh.",
        "Ưu tiên chứng chỉ experimentation design.",
        "Kết nối insight định lượng với phản hồi định tính.",
        "Có lựa chọn làm việc hybrid.",
    ),
    (
        "RECRUITMENT_HR",
        "VIETNAMESE",
        "Chuyên viên tuyển dụng kỹ thuật",
        "Sàng lọc hồ sơ theo tiêu chí đã thống nhất với quản lý.",
        "Điều phối phỏng vấn và tổng hợp phản hồi hội đồng.",
        "Cập nhật trạng thái ứng viên trên hệ thống tuyển dụng.",
        "Có ít nhất 2 năm tuyển dụng vị trí công nghệ.",
        "Tốt nghiệp ngành nhân sự, tâm lý hoặc kinh doanh.",
        "Chứng chỉ tuyển dụng chuyên nghiệp là lợi thế.",
        "Đánh giá ứng viên công bằng và dựa trên bằng chứng nhất quán.",
        "Có thể hỗ trợ sự kiện tuyển dụng cuối tuần.",
    ),
    (
        "RECRUITMENT_HR",
        "VIETNAMESE",
        "Chuyên viên đào tạo nội bộ",
        "Phân tích nhu cầu học tập từ quản lý đơn vị.",
        "Thiết kế buổi thực hành về phản hồi hiệu quả.",
        "Điểm danh người tham dự sau buổi học.",
        "Từ 2 năm thiết kế hoặc điều phối đào tạo.",
        "Bằng đại học giáo dục, nhân sự hoặc truyền thông.",
        "Chứng chỉ đào tạo người lớn được ưu tiên.",
        "Hướng dẫn nhóm đa dạng kinh nghiệm một cách kiên nhẫn.",
        "Làm việc theo lịch đào tạo đã công bố.",
    ),
    (
        "RECRUITMENT_HR",
        "VIETNAMESE",
        "Chuyên viên quan hệ nhân viên",
        "Tiếp nhận và phân loại yêu cầu hỗ trợ nhân sự.",
        "Hòa giải trao đổi giữa các bên theo quy trình nội bộ.",
        "Lưu biên bản xử lý trong hồ sơ được phân quyền.",
        "Có 3 năm làm quan hệ lao động hoặc nhân sự tổng hợp.",
        "Tốt nghiệp luật, quản trị nhân lực hoặc ngành liên quan.",
        "Ưu tiên chứng chỉ tư vấn quan hệ lao động.",
        "Bảo mật thông tin và lắng nghe không phán xét.",
        "Địa điểm làm việc tại Bình Dương.",
    ),
    (
        "RECRUITMENT_HR",
        "VIETNAMESE",
        "Chuyên viên vận hành nhân sự",
        "Kiểm tra dữ liệu nhân viên trước kỳ chốt lương.",
        "Phối hợp cập nhật thay đổi chính sách vào quy trình.",
        "Lưu hồ sơ theo thời hạn lưu trữ quy định.",
        "Tối thiểu 2 năm vận hành nhân sự.",
        "Bằng cao đẳng hoặc đại học ngành quản trị nhân lực.",
        "Chứng chỉ C&B là lợi thế.",
        "Trao đổi thông tin nhạy cảm đúng đối tượng.",
        "Có thể làm thêm trong kỳ chốt lương.",
    ),
    (
        "RECRUITMENT_HR",
        "VIETNAMESE",
        "Chuyên viên phát triển tổ chức",
        "Tổng hợp kết quả khảo sát gắn kết theo đơn vị.",
        "Điều phối workshop xác định hành động cải thiện.",
        "Gửi biên bản họp trong vòng hai ngày làm việc.",
        "Có kinh nghiệm OD hoặc HRBP từ 3 năm.",
        "Tốt nghiệp tâm lý học, nhân sự hoặc quản trị.",
        "Ưu tiên chứng chỉ coaching cơ bản.",
        "Đặt câu hỏi mở để làm rõ nhu cầu của nhóm.",
        "Thường xuyên làm việc với nhiều chi nhánh.",
    ),
    (
        "RECRUITMENT_HR",
        "VIETNAMESE",
        "Chuyên viên tuyển dụng đại trà",
        "Đăng tin và sàng lọc hồ sơ theo kế hoạch tuyển.",
        "Theo dõi tỷ lệ nhận việc và đề xuất cải tiến nguồn.",
        "Gửi lịch phỏng vấn cho ứng viên trước một ngày.",
        "Có 2 năm tuyển dụng khối lượng lớn.",
        "Tốt nghiệp cao đẳng ngành kinh doanh hoặc nhân sự.",
        "Không yêu cầu chứng chỉ bắt buộc.",
        "Thích nghi nhanh khi nhu cầu tuyển thay đổi.",
        "Làm việc tại trung tâm phân phối.",
    ),
    (
        "PROJECT_MANAGEMENT",
        "VIETNAMESE",
        "Điều phối dự án triển khai",
        "Theo dõi mốc triển khai tại từng địa điểm.",
        "Phối hợp xử lý phụ thuộc giữa đội kỹ thuật và vận hành.",
        "Cập nhật action log sau cuộc họp dự án.",
        "Ít nhất 2 năm điều phối dự án triển khai.",
        "Bằng đại học quản trị, kỹ thuật hoặc lĩnh vực liên quan.",
        "PMP certification is preferred.",
        "Nêu rõ rủi ro và chủ sở hữu hành động.",
        "Đi công tác theo lịch dự án.",
    ),
    (
        "PROJECT_MANAGEMENT",
        "VIETNAMESE",
        "Quản lý dự án phần mềm",
        "Xác định phạm vi release với product owner.",
        "Điều phối delivery và xử lý blockers của nhóm.",
        "Lưu quyết định thay đổi trong decision log.",
        "Có 4 năm quản lý dự án phần mềm.",
        "Tốt nghiệp ngành công nghệ hoặc quản trị dự án.",
        "Chứng chỉ Scrum Master là một lợi thế.",
        "Giữ trao đổi minh bạch khi tiến độ thay đổi.",
        "Có thể làm việc với nhóm ở múi giờ khác.",
    ),
    (
        "PROJECT_MANAGEMENT",
        "VIETNAMESE",
        "Chuyên viên quản lý thay đổi",
        "Lập bản đồ nhóm chịu ảnh hưởng bởi thay đổi quy trình.",
        "Đo mức độ sẵn sàng và điều chỉnh kế hoạch hỗ trợ.",
        "Phát hành bản tin thay đổi theo lịch.",
        "Tối thiểu 3 năm triển khai chương trình thay đổi.",
        "Bằng đại học truyền thông, nhân sự hoặc kinh doanh.",
        "Ưu tiên chứng chỉ change management.",
        "Tóm tắt lựa chọn mà không áp đặt kết luận.",
        "Thỉnh thoảng tổ chức workshop ngoài trụ sở.",
    ),
    (
        "PROJECT_MANAGEMENT",
        "VIETNAMESE",
        "Quản lý dự án xây dựng",
        "Theo dõi tiến độ thi công so với baseline.",
        "Phối hợp nhà thầu xử lý giao diện công việc.",
        "Kiểm tra nhật ký công trường cuối ngày.",
        "Có 5 năm quản lý dự án xây dựng.",
        "Bằng kỹ sư xây dựng hoặc quản lý công trình.",
        "Chứng chỉ giám sát thi công còn hiệu lực.",
        "Đàm phán thay đổi bằng dữ kiện và biên bản.",
        "Làm việc chủ yếu tại công trường.",
    ),
    (
        "PROJECT_MANAGEMENT",
        "ENGLISH",
        "Implementation Project Lead",
        "Translate approved scope into a sequenced delivery plan.",
        "Resolve cross-team dependencies before milestone reviews.",
        "Publish a concise weekly status note for sponsors.",
        "At least three years leading client implementations.",
        "A bachelor's degree in business or information systems.",
        "A PRINCE2 credential is an advantage.",
        "Facilitate decisions when stakeholders disagree.",
        "Some regional travel is expected.",
    ),
    (
        "PROJECT_MANAGEMENT",
        "ENGLISH",
        "Portfolio Coordinator",
        "Consolidate milestone data from active initiatives.",
        "Flag schedule conflicts for the portfolio director.",
        "Maintain the shared project register.",
        "Two years in a project coordination role.",
        "A degree in management or a related discipline.",
        "Formal certification is not required.",
        "Communicate schedule conflicts tactfully and clearly.",
        "The role is located near the central office.",
    ),
    (
        "BUSINESS_COMMUNICATION",
        "VIETNAMESE",
        "Chuyên viên truyền thông nội bộ",
        "Lập lịch nội dung cho bản tin nhân viên.",
        "Biên tập thông báo thay đổi chính sách cùng đơn vị phụ trách.",
        "Lưu bản duyệt cuối trong thư viện nội dung.",
        "Có ít nhất 2 năm viết nội dung nội bộ.",
        "Tốt nghiệp báo chí, ngôn ngữ hoặc truyền thông.",
        "Ưu tiên chứng chỉ truyền thông doanh nghiệp.",
        "Viết rõ ràng cho người đọc không chuyên.",
        "Có thể tham dự sự kiện ngoài giờ.",
    ),
    (
        "BUSINESS_COMMUNICATION",
        "VIETNAMESE",
        "Chuyên viên quan hệ báo chí",
        "Soạn thông cáo dựa trên thông tin đã xác minh.",
        "Theo dõi câu hỏi báo chí và phối hợp người phát ngôn.",
        "Lưu danh sách yêu cầu truyền thông theo ngày.",
        "Tối thiểu 3 năm làm báo chí hoặc truyền thông.",
        "Bằng đại học truyền thông, báo chí hoặc ngôn ngữ.",
        "Chứng chỉ media training được ưu tiên.",
        "Phản hồi chính xác dưới áp lực thời hạn.",
        "Sẵn sàng hỗ trợ khi có sự kiện khẩn.",
    ),
    (
        "BUSINESS_COMMUNICATION",
        "VIETNAMESE",
        "Biên tập viên nội dung",
        "Biên tập hướng dẫn sử dụng sản phẩm theo style guide.",
        "Kiểm chứng thuật ngữ với chuyên gia chủ đề.",
        "Đánh dấu bản thảo theo mã phiên bản.",
        "Có 2 năm biên tập nội dung kỹ thuật.",
        "Tốt nghiệp ngôn ngữ, xuất bản hoặc lĩnh vực liên quan.",
        "Ưu tiên chứng chỉ technical writing.",
        "Đưa góp ý cụ thể mà vẫn tôn trọng tác giả.",
        "Có thể làm việc từ xa theo thỏa thuận.",
    ),
    (
        "BUSINESS_COMMUNICATION",
        "VIETNAMESE",
        "Chuyên viên truyền thông khủng hoảng",
        "Theo dõi tín hiệu truyền thông trên các kênh công khai.",
        "Soạn phương án phản hồi theo kịch bản đã duyệt.",
        "Ghi thời điểm phát hành từng thông điệp.",
        "Ít nhất 4 năm xử lý truyền thông doanh nghiệp.",
        "Bằng đại học quan hệ công chúng hoặc báo chí.",
        "Ưu tiên chứng chỉ xử lý khủng hoảng.",
        "Phân biệt thông tin đã xác minh với giả thuyết.",
        "Có lịch trực luân phiên khi phát sinh sự cố.",
    ),
    (
        "BUSINESS_COMMUNICATION",
        "VIETNAMESE",
        "Chuyên viên truyền thông thương hiệu",
        "Triển khai nội dung chiến dịch theo định vị thương hiệu.",
        "Đánh giá phản hồi và đề xuất điều chỉnh thông điệp.",
        "Nộp báo cáo chiến dịch theo mẫu thống nhất.",
        "Có kinh nghiệm truyền thông thương hiệu từ 2 năm.",
        "Tốt nghiệp marketing, ngôn ngữ hoặc truyền thông.",
        "Không bắt buộc chứng chỉ chuyên môn.",
        "Phối hợp nhiều nhóm mà không làm mất nhất quán thông điệp.",
        "Mức đãi ngộ trao đổi khi phỏng vấn.",
    ),
    (
        "BUSINESS_COMMUNICATION",
        "VIETNAMESE",
        "Chuyên viên đào tạo kỹ năng viết",
        "Đánh giá mẫu email để xác định lỗi giao tiếp phổ biến.",
        "Thiết kế bài tập viết phản hồi cho tình huống khách hàng.",
        "Điểm danh học viên trong từng lớp.",
        "Có 3 năm đào tạo hoặc biên tập văn bản.",
        "Bằng đại học sư phạm, ngôn ngữ hoặc truyền thông.",
        "Chứng chỉ đào tạo người lớn là lợi thế.",
        "Điều chỉnh cách giải thích theo trình độ người học.",
        "Lớp học có thể tổ chức tại nhiều chi nhánh.",
    ),
    (
        "DATA_ANALYTICS",
        "ENGLISH",
        "Customer Insights Analyst",
        "Segment survey responses by customer lifecycle stage.",
        "Quantify retention patterns and explain uncertainty.",
        "Upload the approved monthly insight deck.",
        "Three years conducting customer or market analysis.",
        "A degree in statistics, economics, or social science.",
        "A market research qualification is preferred.",
        "Good professional skills are needed.",
        "The team offers flexible office days.",
    ),
    (
        "RECRUITMENT_HR",
        "ENGLISH",
        "People Operations Partner",
        "Review workforce requests against approved headcount.",
        "Coach managers through documented performance conversations.",
        "File signed policy acknowledgements in the employee record.",
        "Four years in HR operations or business partnering.",
        "A degree in human resources, law, or business.",
        "CIPD certification is desirable.",
        "Handle sensitive conversations with care and impartiality.",
        "The role supports multiple office locations.",
    ),
    (
        "PROJECT_MANAGEMENT",
        "ENGLISH",
        "Public Program Coordinator",
        "Track grant deliverables against the approved workplan.",
        "Coordinate partner reviews and resolve reporting gaps.",
        "Archive signed attendance sheets after each session.",
        "Two years coordinating funded programs.",
        "A bachelor's degree in public administration or a related field.",
        "A project management certificate is preferred.",
        "Summarize partner concerns without changing their meaning.",
        "Some meetings take place outside standard hours.",
    ),
    (
        "BUSINESS_COMMUNICATION",
        "ENGLISH",
        "Executive Communications Writer",
        "Draft leadership messages using approved business facts.",
        "Edit quarterly updates for clarity and audience fit.",
        "Route each final draft through the approval checklist.",
        "Five years writing executive or corporate communications.",
        "A degree in communications, journalism, or English.",
        "A professional editing credential is optional.",
        "Collaborate effectively with editors and communications partners.",
        "Compensation is discussed with shortlisted applicants.",
    ),
    (
        "FINANCE_ACCOUNTING",
        "VIETNAMESE",
        "Kế toán quản trị",
        "Phân bổ chi phí dùng chung theo tiêu thức đã phê duyệt.",
        "So sánh kết quả thực tế với kế hoạch và giải thích chênh lệch.",
        "Lập bảng đối chiếu vào ngày chốt kỳ.",
        "Có 3 năm làm kế toán quản trị.",
        "Tốt nghiệp đại học kế toán hoặc quản trị kinh doanh.",
        "Ưu tiên chứng chỉ CMA.",
        "Đặt câu hỏi để kiểm tra tính hợp lý của giả định.",
        "Nơi làm việc có bãi đỗ xe.",
    ),
    (
        "SOFTWARE_ENGINEERING",
        "VIETNAMESE",
        "Kỹ sư tích hợp hệ thống",
        "Kết nối dịch vụ nội bộ qua hợp đồng API có phiên bản.",
        "Xử lý retry và lỗi trùng thông điệp trong consumer.",
        "Cập nhật sơ đồ tích hợp sau khi phát hành.",
        "Từ 3 năm xây dựng tích hợp hệ thống.",
        "Bằng đại học phần mềm hoặc kỹ thuật máy tính.",
        "Ưu tiên chứng chỉ integration platform.",
        "Phân tích lỗi liên hệ thống theo từng bước.",
        "Có thể tham gia trực hỗ trợ theo quý.",
    ),
    (
        "DATA_ANALYTICS",
        "VIETNAMESE",
        "Chuyên viên quản trị dữ liệu",
        "Xác định quy tắc kiểm tra chất lượng cho bộ dữ liệu chủ.",
        "Điều tra sai lệch và phối hợp chủ dữ liệu khắc phục.",
        "Cập nhật danh mục thuật ngữ đã được duyệt.",
        "Có 2 năm làm quản trị hoặc chất lượng dữ liệu.",
        "Bằng đại học hệ thống thông tin hoặc thống kê.",
        "Chứng chỉ data governance là lợi thế.",
        "Giải thích trách nhiệm dữ liệu cho nhiều nhóm.",
        "Có thể làm việc tại chi nhánh miền Nam.",
    ),
    (
        "RECRUITMENT_HR",
        "VIETNAMESE",
        "Chuyên viên phân tích nhân lực",
        "Tổng hợp biến động nhân sự theo đơn vị và thời gian.",
        "Kiểm tra giả định trước khi trình bày dự báo nghỉ việc.",
        "Lưu định nghĩa chỉ số nhân lực trong catalog.",
        "Tối thiểu 2 năm phân tích dữ liệu nhân sự.",
        "Bằng đại học thống kê, nhân sự hoặc kinh tế.",
        "Ưu tiên chứng chỉ people analytics.",
        "Trình bày hạn chế mẫu số rõ ràng.",
        "Chính sách nghỉ phép theo quy định hiện hành.",
    ),
    (
        "PROJECT_MANAGEMENT",
        "VIETNAMESE",
        "Điều phối dự án sự kiện",
        "Xây dựng timeline cho chuỗi hội thảo khách hàng.",
        "Điều phối nhà cung cấp và phương án dự phòng địa điểm.",
        "Kiểm đếm vật tư sau từng sự kiện.",
        "Có 2 năm điều phối sự kiện hoặc dự án.",
        "Tốt nghiệp quản trị, truyền thông hoặc du lịch.",
        "Chứng chỉ quản lý sự kiện không bắt buộc.",
        "Giữ bình tĩnh khi lịch trình thay đổi sát giờ.",
        "Làm việc cuối tuần theo lịch sự kiện.",
    ),
    (
        "BUSINESS_COMMUNICATION",
        "VIETNAMESE",
        "Chuyên viên bản địa hóa",
        "Chuyển ngữ hướng dẫn sản phẩm sang tiếng Việt tự nhiên.",
        "Đối chiếu bản dịch với glossary sản phẩm đã duyệt.",
        "Ghi nhận yêu cầu sửa thuật ngữ trong bảng theo dõi.",
        "Có ít nhất 2 năm bản địa hóa nội dung số.",
        "Tốt nghiệp ngôn ngữ Anh hoặc ngành tương đương.",
        "Ưu tiên chứng chỉ dịch thuật chuyên ngành.",
        "Bảo toàn sắc thái và điều kiện trong thông điệp gốc.",
        "Có thể làm việc theo lịch phát hành.",
    ),
]

BOUNDARY_TAGS = [
    "responsibility_vs_experience",
    "responsibility_vs_behavioral",
    "experience_with_capability_signal",
    "education_not_capability",
    "qualification_not_capability",
    "behavioral_capability_candidate",
    "generic_behavior_not_capability",
    "age_or_personal_condition_other",
    "salary_benefit_other",
    "location_or_schedule_other",
    "mixed_requirement_clause",
    "coordinated_clause_split",
    "coordinated_clause_keep",
    "html_list_boundary",
    "html_inline_formatting",
    "duplicate_semantics_across_source_fields",
    "weak_preference_language",
    "mandatory_vs_preferred",
    "years_experience_not_level",
    "degree_subject_not_capability",
    "certificate_not_capability",
    "tool_mention_in_responsibility",
    "tool_mention_without_capability",
    "generic_keyword_overlap",
    "mixed_language",
]
DOMAIN_LIMITS = {
    "FINANCE_ACCOUNTING": 8,
    "SOFTWARE_ENGINEERING": 8,
    "DATA_ANALYTICS": 6,
    "RECRUITMENT_HR": 6,
    "PROJECT_MANAGEMENT": 6,
    "BUSINESS_COMMUNICATION": 6,
}
ENGLISH_TITLES = {
    "Treasury Operations Analyst",
    "Revenue Assurance Specialist",
    "Data Platform Engineer",
    "Application Support Developer",
    "Customer Insights Analyst",
    "People Operations Partner",
    "Implementation Project Lead",
    "Public Program Coordinator",
    "Executive Communications Writer",
}
MIXED_TITLES = {
    "Chuyên viên công nợ",
    "Kỹ sư backend",
    "Chuyên viên phân tích dữ liệu",
    "Chuyên viên tuyển dụng kỹ thuật",
    "Quản lý dự án phần mềm",
    "Chuyên viên truyền thông nội bộ",
}
TAG_CASES = {
    "responsibility_vs_experience": 1,
    "responsibility_vs_behavioral": 2,
    "experience_with_capability_signal": 3,
    "education_not_capability": 4,
    "qualification_not_capability": 5,
    "behavioral_capability_candidate": 3,
    "generic_behavior_not_capability": 8,
    "age_or_personal_condition_other": 18,
    "salary_benefit_other": 2,
    "location_or_schedule_other": 3,
    "mixed_requirement_clause": 11,
    "coordinated_clause_split": 10,
    "coordinated_clause_keep": 3,
    "html_list_boundary": 1,
    "html_inline_formatting": 1,
    "duplicate_semantics_across_source_fields": 9,
    "weak_preference_language": 1,
    "mandatory_vs_preferred": 2,
    "years_experience_not_level": 3,
    "degree_subject_not_capability": 4,
    "certificate_not_capability": 5,
    "tool_mention_in_responsibility": 9,
    "tool_mention_without_capability": 22,
    "generic_keyword_overlap": 35,
    "mixed_language": 1,
}
SOURCE_STATE_CASES = {
    1: ("job_requirements_html", "OMITTED"),
    2: ("job_requirements_html", "NULL"),
    3: ("job_requirements_html", "EMPTY"),
    4: ("job_requirements_html", "WHITESPACE"),
    5: ("job_description_html", "OMITTED"),
    6: ("job_description_html", "NULL"),
}
NONCAP_ROUTINE_CASES = {3, 5, 7, 8, 12, 16, 21, 28}
BEHAVIOR_AS_RESPONSIBILITY_TITLES = {
    "Treasury Operations Analyst",
    "Nhà phân tích sản phẩm",
    "Portfolio Coordinator",
    "Public Program Coordinator",
    "Implementation Project Lead",
}
VAGUE_BEHAVIOR_BY_CASE = {
    2: "Có thái độ phù hợp với công việc.",
    4: "Có năng lực chuyên môn phù hợp.",
    6: "Đáp ứng kỳ vọng nghề nghiệp của vị trí.",
    8: "Good professional skills are required.",
    10: "Có phong cách làm việc phù hợp.",
    12: "Thể hiện năng lực tổng thể tốt.",
    14: "Có tố chất cần thiết cho công việc.",
    16: "Strong overall aptitude required.",
    18: "Đáp ứng yêu cầu chung của vị trí.",
    20: "Có năng lực phù hợp với vai trò.",
    22: "Good professional skills are needed.",
    24: "Thể hiện năng lực phù hợp với kỳ vọng.",
}


def render() -> list[dict[str, object]]:
    cases: list[dict[str, object]] = []
    selected: list[tuple[str, ...]] = []
    domain_seen: dict[str, int] = {}
    for row in ROWS:
        domain = row[0]
        if domain_seen.get(domain, 0) >= DOMAIN_LIMITS[domain]:
            continue
        # Prefer the selected original English postings while preserving the
        # exact approved domain distribution.
        selected.append(row)
        domain_seen[domain] = domain_seen.get(domain, 0) + 1
    # Swap later same-domain Vietnamese rows for authored English rows beyond
    # the initial domain slice while keeping the domain quotas exact.
    for domain in DOMAIN_LIMITS:
        assert sum(row[0] == domain for row in selected) == DOMAIN_LIMITS[domain]
    selected_titles = {row[2] for row in selected}
    for row in ROWS:
        if row[2] not in ENGLISH_TITLES or row[2] in selected_titles:
            continue
        domain = row[0]
        replace_at = next(
            (
                i
                for i in range(len(selected) - 1, -1, -1)
                if selected[i][0] == domain and selected[i][1] == "VIETNAMESE"
            ),
            None,
        )
        if replace_at is not None:
            selected_titles.remove(selected[replace_at][2])
            selected[replace_at] = row
            selected_titles.add(row[2])

    for index, row in enumerate(selected, start=1):
        (
            domain,
            language,
            title,
            duty_a,
            duty_b,
            routine,
            experience,
            education,
            credential,
            behavior,
            other,
        ) = row
        language = "ENGLISH" if title in ENGLISH_TITLES else language
        if title in MIXED_TITLES:
            language = "MIXED"
        if title == "Chuyên viên công nợ":
            duty_a = "Reconcile công nợ khách hàng theo từng kỳ."
        if title == "Kỹ sư backend":
            duty_b = duty_a
        if title == "Kỹ sư frontend":
            duty_a = "Thiết kế màn hình quản lý đơn hàng và kiểm thử luồng thanh toán."
        if title == "Chuyên viên phân tích vận hành":
            other = "Ứng viên trong độ tuổi từ 25 đến 35 có thể nộp hồ sơ."
        if title == "Customer Insights Analyst":
            other = "The team uses Tableau; prior Tableau expertise is not required."
        behavior = VAGUE_BEHAVIOR_BY_CASE.get(index, behavior)
        behavior_type = (
            "RESPONSIBILITY"
            if title in BEHAVIOR_AS_RESPONSIBILITY_TITLES
            else "BEHAVIORAL_REQUIREMENT"
        )
        include_both_credentials = index <= 20
        statements: list[dict[str, object]] = []
        source_items: dict[str, list[str]] = {"JOB_DESCRIPTION": [], "JOB_REQUIREMENTS": []}
        clauses = [
            (duty_a, "RESPONSIBILITY", "CAPABILITY_BEARING", "JOB_DESCRIPTION"),
            # These are role-specific control/documentation duties, not generic
            # personal traits; the responsibility text itself is the signal.
            (
                routine,
                "RESPONSIBILITY",
                "NON_CAPABILITY" if index in NONCAP_ROUTINE_CASES else "CAPABILITY_BEARING",
                "JOB_DESCRIPTION",
            ),
            (experience, "EXPERIENCE_REQUIREMENT", "CAPABILITY_BEARING", "JOB_REQUIREMENTS"),
            (duty_b, "RESPONSIBILITY", "CAPABILITY_BEARING", "JOB_REQUIREMENTS"),
            (
                behavior,
                behavior_type,
                "UNCLEAR" if index in VAGUE_BEHAVIOR_BY_CASE else "CAPABILITY_BEARING",
                "JOB_DESCRIPTION",
            ),
            (other, "OTHER", "NON_CAPABILITY", "JOB_REQUIREMENTS"),
        ]
        qualification_type = "EDUCATION_REQUIREMENT" if index % 2 else "QUALIFICATION_REQUIREMENT"
        clauses.append(
            (
                education if qualification_type == "EDUCATION_REQUIREMENT" else credential,
                qualification_type,
                "NON_CAPABILITY",
                "JOB_DESCRIPTION",
            )
        )
        if include_both_credentials:
            clauses.append(
                (
                    credential if qualification_type == "EDUCATION_REQUIREMENT" else education,
                    "QUALIFICATION_REQUIREMENT"
                    if qualification_type == "EDUCATION_REQUIREMENT"
                    else "EDUCATION_REQUIREMENT",
                    "NON_CAPABILITY",
                    "JOB_REQUIREMENTS",
                )
            )
        source_state = SOURCE_STATE_CASES.get(index)
        one_sided_field = None
        if source_state:
            absent_field, _ = source_state
            one_sided_field = (
                "JOB_REQUIREMENTS" if absent_field == "job_description_html" else "JOB_DESCRIPTION"
            )
        if title == "Kỹ sư nền tảng":
            clauses = [
                (
                    text,
                    kind,
                    relevance,
                    "JOB_REQUIREMENTS" if kind == "EDUCATION_REQUIREMENT" else field,
                )
                for text, kind, relevance, field in clauses
            ]

        field_orders = {"JOB_DESCRIPTION": 0, "JOB_REQUIREMENTS": 0}
        for text, kind, relevance, source_field in clauses:
            source_field = one_sided_field or source_field
            pieces = (
                ("Thiết kế màn hình quản lý đơn hàng", "kiểm thử luồng thanh toán.")
                if title == "Kỹ sư frontend" and text == duty_a
                else (text,)
            )
            source_items[source_field].append(text)
            for piece in pieces:
                field_orders[source_field] += 1
                statement_id = f"jd-syn-v1-{index:03d}-s{len(statements) + 1:02d}"
                statements.append(
                    {
                        "statement_id": statement_id,
                        "source_field": source_field,
                        "source_text": piece,
                        "normalized_statement": piece,
                        "statement_type": kind,
                        "capability_relevance": relevance,
                        "source_order": field_orders[source_field],
                        "label_source": "synthetic_spec",
                        "review_status": "REVIEWED",
                    }
                )

        if title == "Kỹ sư nền tảng":
            req_items = source_items["JOB_REQUIREMENTS"]
            req_items[req_items.index(experience)] = f"{experience} và {education}"
            if education in source_items["JOB_DESCRIPTION"]:
                source_items["JOB_DESCRIPTION"].remove(education)
            if education in req_items:
                req_items.remove(education)
            for statement in statements:
                if statement["statement_type"] == "EDUCATION_REQUIREMENT":
                    statement["source_order"] = 2
                elif statement["source_field"] == "JOB_REQUIREMENTS":
                    if statement["statement_type"] == "EXPERIENCE_REQUIREMENT":
                        statement["source_order"] = 1
                    elif statement["statement_type"] == "RESPONSIBILITY":
                        statement["source_order"] = 3
                    elif statement["statement_type"] == "OTHER":
                        statement["source_order"] = 4
                    elif statement["statement_type"] == "QUALIFICATION_REQUIREMENT":
                        statement["source_order"] = 5
        description_html = (
            f"<h2>{html.escape(title)}</h2><ul>"
            + "".join(
                f"<li>{'<strong>' + html.escape(text.split(' ', 1)[0]) + '</strong>' + (' ' + html.escape(text.split(' ', 1)[1]) if ' ' in text else '') if index == 1 and item_index == 0 else html.escape(text)}</li>"
                for item_index, text in enumerate(source_items["JOB_DESCRIPTION"])
            )
            + "</ul>"
        )
        heading = (
            "<p>Yêu cầu công việc / Role requirements</p>"
            if language == "MIXED"
            else "<p>Role requirements</p>"
        )
        requirements_html = (
            heading
            + "<ol>"
            + "".join(f"<li>{html.escape(text)}</li>" for text in source_items["JOB_REQUIREMENTS"])
            + "</ol>"
        )
        source_record: dict[str, object] = {
            "source_application_ref": f"synthetic-application-{index:03d}",
            "job_description_html": description_html,
            "job_requirements_html": requirements_html,
            "job_posting_url": f"https://example.invalid/posting/{index:03d}",
        }
        if source_state:
            field, state = source_state
            if state == "OMITTED":
                source_record.pop(field)
            elif state == "NULL":
                source_record[field] = None
            elif state == "EMPTY":
                source_record[field] = ""
            else:
                source_record[field] = " \t "
        cases.append(
            {
                "case_id": f"jd-syn-v1-{index:03d}",
                "source_application_ref": f"synthetic-application-{index:03d}",
                "target_job_source": source_record,
                "expected_statements": statements,
                "language_profile": language,
                "domain": domain,
                "difficulty": ("EASY", "MEDIUM", "HARD")[(index - 1) % 3],
                "boundary_tags": [],
                "label_source": "synthetic_spec",
            }
        )
    # Guarantee each required tag is included; one case may carry several tags.
    for tag, case_number in TAG_CASES.items():
        target = cases[case_number - 1]
        target["boundary_tags"] = sorted(set(target["boundary_tags"]) | {tag})
    return cases


if __name__ == "__main__":
    output = ROOT / "dataset.synthetic.v1.jsonl"
    output.write_text(
        "".join(
            json.dumps(case, ensure_ascii=False, separators=(",", ":")) + "\n" for case in render()
        ),
        encoding="utf-8",
    )
    print(f"wrote {len(render())} synthetic cases to {output}")
