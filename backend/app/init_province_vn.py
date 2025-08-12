import os
import psycopg
from psycopg import sql

# Cấu hình kết nối PostgreSQL
DB_NAME = "db_fastapi"
DB_USER = "postgres"  # Thay đổi user của bạn
DB_PASSWORD = "Kh0ngbiet"  # Thay đổi password của bạn
DB_HOST = "192.168.1.80" # Thay đổi host của bạn
DB_PORT = "5432"      # Thay đổi port của bạn


def run_sql_script(sql_file_path: str):
    """
    Kết nối đến database PostgreSQL và thực thi các câu lệnh từ một file SQL.
    """
    if not os.path.exists(sql_file_path):
        print(f"Lỗi: Không tìm thấy file SQL tại đường dẫn '{sql_file_path}'.")
        return

    print(f"Đang kết nối tới database PostgreSQL: {DB_HOST}:{DB_PORT}/{DB_NAME}")
    print(f"Đang thực thi các câu lệnh từ file: {sql_file_path}")

    try:
        # Tạo chuỗi kết nối
        conn_string = f"dbname={DB_NAME} user={DB_USER} password={DB_PASSWORD} host={DB_HOST} port={DB_PORT}"
        
        with psycopg.connect(conn_string) as conn:
            with conn.cursor() as cursor:
                with open(sql_file_path, 'r', encoding='utf-8') as file:
                    sql_script = file.read()
                    
                    # Tách các câu lệnh SQL bằng dấu chấm phẩy và bỏ qua các dòng trống
                    sql_statements = [s.strip() for s in sql_script.split(';') if s.strip()]
                    
                    for statement in sql_statements:
                        try:
                            cursor.execute(statement)
                        except psycopg.IntegrityError as e:
                            # Bắt lỗi khi dữ liệu bị trùng lặp và bỏ qua để tiếp tục
                            print(f"Cảnh báo: Lỗi trùng lặp dữ liệu. Bỏ qua câu lệnh: '{statement[:50]}...'")
                            print(f"Chi tiết lỗi: {e}")
                            conn.rollback() # Hoàn tác giao dịch để tiếp tục
                        except Exception as e:
                            print(f"Lỗi khi thực thi câu lệnh SQL: '{statement[:50]}...'")
                            print(f"Chi tiết lỗi: {e}")
                            conn.rollback()
                            raise
            conn.commit()
        print("\nHoàn tất cập nhật database thành công.")

    except Exception as e:
        print(f"Đã xảy ra lỗi nghiêm trọng khi kết nối hoặc thực thi SQL: {e}")

if __name__ == "__main__":
    # Thay đổi tên file SQL nếu cần thiết
    sql_file = "ImportData_vn_units.sql"
    run_sql_script(sql_file)

