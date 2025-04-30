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

running = True

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
sheet = client.open("Userdata").sheet1

# เชื่อมต่อ ESP32
serial_port = find_serial_port()
if serial_port:
    ser = serial.Serial(serial_port, 115200, timeout=2)
else:
    print("ไม่พบ ESP32! โปรดเชื่อมต่อแล้วลองใหม่")
    exit()

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

# ฟังก์ชันอัปเดตคะแนนใน Google Sheets
def update_user_score(user_id, new_score):
    try:
        cell = sheet.find(user_id)
        if cell:
            print(f"Updating {user_id} to new score: {new_score}")
            sheet.update_cell(cell.row, 3, new_score)
    except Exception as e:
        print(f"Error updating Google Sheets: {e}")

# ฟังก์ชัน Restart GUI
def restart_gui():
    print("Restarting GUI...")
    global running
    running = False
    ser.close()
    os.execl(sys.executable, sys.executable, *sys.argv)

# ฟังก์ชันล็อกอินและส่งข้อมูลไปยัง ESP32
def barcode_scanned(event=None):
    user_id = entry.get().strip()
    if not user_id:
        status_label.config(text="กรุณากรอก ID", fg="#e53935")
        return

    user_name, user_score = get_user_info(user_id)
    if user_name:
        data_to_send = f"{user_id},{user_name},{user_score}\n"
        ser.write(data_to_send.encode())
        time.sleep(1)
        status_label.config(text=f"ยินดีต้อนรับ {user_name}!", fg="#4caf50")
    else:
        status_label.config(text="ไม่พบผู้ใช้!", fg="#e53935")
    
    entry.delete(0, tk.END)

# ฟังก์ชันรับข้อมูลจาก ESP32 และอัปเดตคะแนนใน Google Sheets
last_score = None
last_update_time = time.time()

def listen_for_scores():
    global last_score, last_update_time, running
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

                        if new_score != last_score:
                            last_score = new_score
                            last_update_time = time.time()
                        
                        update_user_score(user_id, new_score)
                        print(f"Updated {user_name} ({user_id}) score: {new_score}")

            if time.time() - last_update_time >= 120:
                restart_gui()

        except Exception as e:
            print("เกิดข้อผิดพลาด:", e)

# ฟังก์ชันปิดโปรแกรมอย่างสมบูรณ์
def on_closing():
    global running
    running = False
    ser.close()
    root.destroy()

# ฟังก์ชันจัดกึ่งกลางหน้าจอ
def center_window(root, width=400, height=300):
    screen_width = root.winfo_screenwidth()
    screen_height = root.winfo_screenheight()
    
    position_x = (screen_width // 2) - (width // 2)
    position_y = (screen_height // 2) - (height // 2)
    
    root.geometry(f"{width}x{height}+{position_x}+{position_y}")

# -------------------------- เริ่มสร้าง GUI ---------------------------
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

# เพิ่มปุ่ม Reset GUI
reset_button = tk.Button(root, text="🔄 Reset", font=text_font, bg="#2196f3", fg="white", command=restart_gui)
reset_button.pack(pady=(5, 10))

exit_button = tk.Button(root, text="❌ Exit", font=text_font, bg="#e53935", fg="white", command=on_closing)
exit_button.pack(pady=(10, 20))

entry.focus_set()
entry.bind("<Return>", barcode_scanned)

root.protocol("WM_DELETE_WINDOW", on_closing)

# เริ่มรับข้อมูลคะแนนจาก ESP32
score_thread = threading.Thread(target=listen_for_scores, daemon=True)
score_thread.start()

root.mainloop()
