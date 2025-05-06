import gspread
from oauth2client.service_account import ServiceAccountCredentials
import serial
import serial.tools.list_ports
import time
import threading
import tkinter as tk
from tkinter import font as tkfont
import os
import sys
from datetime import datetime

running = True
current_log_row = None
session_score = 0  # 🟩 คะแนน session ล่าสุด (ไม่เกี่ยวกับคะแนนสะสม)

# ค้นหาพอร์ตของ ESP32 อัตโนมัติ
def find_serial_port():
    ports = serial.tools.list_ports.comports()
    for port in ports:
        if "USB" in port.description or "COM" in port.device:
            return port.device
    return None

# ตั้งค่า Google Sheets API
creds = ServiceAccountCredentials.from_json_keyfile_name("credentials.json", scopes=[
    "https://spreadsheets.google.com/feeds",
    "https://www.googleapis.com/auth/spreadsheets",
    "https://www.googleapis.com/auth/drive.file",
    "https://www.googleapis.com/auth/drive"
])
client = gspread.authorize(creds)
spreadsheet = client.open("Userdata")
sheet = spreadsheet.worksheet("sheet1")     # คะแนนสะสม
sheet_log = spreadsheet.worksheet("log")     # Log session ปัจจุบัน

# ฟังก์ชันดึงข้อมูลผู้ใช้จาก Google Sheets
def get_user_info(user_id):
    try:
        cell = sheet.find(user_id)
        if cell:
            user_name = sheet.cell(cell.row, 2).value
            user_score = int(sheet.cell(cell.row, 3).value or 0)
            return user_name, user_score
    except:
        pass
    return None, None

# อัปเดตคะแนนสะสมรวมใน sheet1
def update_user_score(user_id, new_total_score):
    try:
        cell = sheet.find(user_id)
        if cell:
            sheet.update_cell(cell.row, 3, new_total_score)
    except Exception as e:
        print(f"Error updating user score: {e}")

# เริ่มบันทึก log ใหม่เมื่อ Login
def start_log_record(user_id, user_name, score):
    global current_log_row
    timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    sheet_log.append_row([user_id, user_name, score, timestamp])
    current_log_row = len(sheet_log.get_all_values())  # แถว log ปัจจุบัน

# อัปเดต log ในแถวเดิม
def update_log_score(score):
    global current_log_row
    if current_log_row:
        timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        try:
            sheet_log.update_cell(current_log_row, 3, score)
            sheet_log.update_cell(current_log_row, 4, timestamp)
        except Exception as e:
            print(f"Error updating log row: {e}")

# ล้าง log row
def reset_log_row():
    global current_log_row, session_score
    current_log_row = None
    session_score = 0

# ฟังก์ชัน Restart GUI
def restart_gui():
    global running
    running = False
    reset_log_row()
    ser.close()
    os.execl(sys.executable, sys.executable, *sys.argv)

# ฟังก์ชันล็อกอินและส่งข้อมูลไปยัง ESP32
def barcode_scanned(event=None):
    global session_score
    user_id = entry.get().strip()
    if not user_id:
        status_label.config(text="กรุณากรอก ID", fg="#e53935")
        return

    user_name, user_score = get_user_info(user_id)
    if user_name:
        session_score = 0  # 🟩 รีเซ็ตคะแนน session ใหม่
        data_to_send = f"{user_id},{user_name},{session_score}\n"
        ser.write(data_to_send.encode())
        time.sleep(1)
        status_label.config(text=f"ยินดีต้อนรับ {user_name}!", fg="#4caf50")
        start_log_record(user_id, user_name, session_score)
    else:
        status_label.config(text="ไม่พบผู้ใช้!", fg="#e53935")

    entry.delete(0, tk.END)

# รับข้อมูลจาก ESP32 และอัปเดตคะแนน
last_score = None
last_update_time = time.time()

def listen_for_scores():
    global last_score, last_update_time, running, session_score
    while running:
        try:
            if ser.in_waiting:
                data = ser.readline().decode().strip()
                print(f"Received: {data}")

                parts = data.split(",")
                if len(parts) == 3:
                    user_id = parts[0].strip()
                    user_name = parts[1].strip()
                    new_score = parts[2].strip()

                    if new_score.isdigit():
                        new_score = int(new_score)

                        # เช็กว่าคะแนน session เปลี่ยนแปลง
                        if new_score != last_score:
                            last_score = new_score
                            session_score = new_score
                            last_update_time = time.time()

                            # ดึงคะแนนสะสมเดิมจาก sheet1
                            _, total_before = get_user_info(user_id)
                            total_after = total_before + session_score
                            update_user_score(user_id, total_after)
                            update_log_score(session_score)

                            print(f"Updated {user_name} ({user_id}) session: {session_score}, total: {total_after}")

            if time.time() - last_update_time >= 120:
                restart_gui()

        except Exception as e:
            print("เกิดข้อผิดพลาด:", e)

# ปิดโปรแกรม
def on_closing():
    global running
    running = False
    reset_log_row()
    ser.close()
    root.destroy()

# จัดกึ่งกลางหน้าจอ
def center_window(root, width=400, height=300):
    screen_width = root.winfo_screenwidth()
    screen_height = root.winfo_screenheight()
    position_x = (screen_width // 2) - (width // 2)
    position_y = (screen_height // 2) - (height // 2)
    root.geometry(f"{width}x{height}+{position_x}+{position_y}")

# ---------------- GUI ----------------
serial_port = find_serial_port()
if serial_port:
    ser = serial.Serial(serial_port, 115200, timeout=2)
else:
    print("ไม่พบ ESP32! โปรดเชื่อมต่อแล้วลองใหม่")
    exit()

root = tk.Tk()
root.title("🚀 Login System")
root.configure(bg="#f0f4f8")
center_window(root)

header_font = tkfont.Font(family="Helvetica", size=18, weight="bold")
text_font = tkfont.Font(family="Helvetica", size=12)

header_label = tk.Label(root, text="🔍 Enter Student ID", font=header_font, bg="#f0f4f8", fg="#333")
header_label.pack(pady=(20, 10))

frame = tk.Frame(root, bg="#f0f4f8")
frame.pack(pady=10)

entry = tk.Entry(frame, font=text_font, width=25, bd=3, relief="groove")
entry.grid(row=0, column=0, padx=(0,10))

login_button = tk.Button(frame, text="✅ Login", font=text_font, bg="#4caf50", fg="white", command=barcode_scanned)
login_button.grid(row=0, column=1)

status_label = tk.Label(root, text="", font=text_font, bg="#f0f4f8", fg="#e53935")
status_label.pack(pady=10)

reset_button = tk.Button(root, text="🔄 Reset", font=text_font, bg="#2196f3", fg="white", command=restart_gui)
reset_button.pack(pady=(5, 10))

exit_button = tk.Button(root, text="❌ Exit", font=text_font, bg="#e53935", fg="white", command=on_closing)
exit_button.pack(pady=(10, 20))

entry.focus_set()
entry.bind("<Return>", barcode_scanned)

root.protocol("WM_DELETE_WINDOW", on_closing)

score_thread = threading.Thread(target=listen_for_scores, daemon=True)
score_thread.start()

root.mainloop()
