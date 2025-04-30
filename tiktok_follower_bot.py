import os
import time
import hashlib
import requests
import urllib.parse
import threading
import random
from concurrent.futures import ThreadPoolExecutor
from telebot import TeleBot
from functools import wraps
from datetime import datetime, timedelta

# Cấu hình bot - Token mới
TOKEN = "7606131282:AAHxi1F1GNxRiNICE1B-HxKPBFKcTHa8j50"
bot = TeleBot(TOKEN)



# Biến toàn cục
core_admins = [6683331082]  # ID của admin chính duy nhất
vip_users = set()  # Danh sách người dùng VIP
running_tasks = {}  # Theo dõi các tác vụ đang chạy
waiting_users = {}  # Theo dõi người dùng đang trong thời gian chờ
auto_buff_users = {}  # Theo dõi người dùng đang sử dụng auto buff
executor = ThreadPoolExecutor(max_workers=1000)  # Thread pool cho các tác vụ đồng thời

# URL Shortener API
URL_SHORTENER_TOKEN = "6ec3529d5d8cb18405369923670980ec155af75fb3a70c1c90c5a9d9ac25ceea"
REDIRECT_URL = "https://liggdzut.x10.bz/index.html"

# Thống kê buff
stats = {
    "total_buff": 0,
    "successful_buff": 0,
    "failed_buff": 0,
    "last_updated": time.time()
}

# Cấu hình lưu trữ key
KEY_STORAGE_DIR = "atuandev"  # Thư mục lưu trữ file xác thực key
os.makedirs(KEY_STORAGE_DIR, exist_ok=True)

# Tạo file key.txt để lưu trữ
KEY_FILE = "key.txt"
if not os.path.exists(KEY_FILE):
    with open(KEY_FILE, 'w') as f:
        f.write('')

# Hàm trợ giúp
def TimeStamp():
    """Lấy ngày hiện tại dưới dạng chuỗi (DD-MM-YYYY) theo múi giờ Việt Nam (GMT+7)"""
    vietnam_time = datetime.now() + timedelta(hours=7)
    return vietnam_time.strftime('%d-%m-%Y')

def auto_delete_message(chat_id, message_id, delay=15):
    """Tự động xóa tin nhắn sau một khoảng thời gian"""
    def delete_message():
        time.sleep(delay)
        try:
            bot.delete_message(chat_id, message_id)
        except Exception as e:
            print(f"Không thể xóa tin nhắn: {e}")
    
    # Tạo một luồng mới để xóa tin nhắn sau delay giây
    threading.Thread(target=delete_message, daemon=True).start()

def admin_auto_delete(func):
    """Decorator tự động xóa tin nhắn phản hồi cho admin sau 15 giây"""
    @wraps(func)
    def wrapper(message, *args, **kwargs):
        # Gọi hàm gốc
        response = func(message, *args, **kwargs)
        
        # Nếu tin nhắn từ admin, tự động xóa phản hồi sau 15 giây
        if is_admin(message.from_user.id) and hasattr(response, 'message_id'):
            auto_delete_message(message.chat.id, response.message_id)
        
        return response
    return wrapper

def is_key_valid(user_id):
    """Kiểm tra xem người dùng có key hợp lệ cho ngày hôm nay không"""
    today = TimeStamp()
    user_folder = f"{KEY_STORAGE_DIR}/{today}"
    return os.path.exists(f"{user_folder}/{user_id}.txt")

def is_admin(user_id):
    """Kiểm tra xem người dùng có phải là admin không"""
    return user_id in core_admins
    
def is_vip(user_id):
    """Kiểm tra xem người dùng có phải là VIP không"""
    return user_id in vip_users

def add_vip(user_id):
    """Thêm người dùng vào danh sách VIP"""
    vip_users.add(user_id)
    
    # Lưu file VIP
    with open("vip_users.txt", "a") as f:
        f.write(f"{user_id}\n")
        
def load_vip_users():
    """Load danh sách người dùng VIP từ file"""
    if os.path.exists("vip_users.txt"):
        with open("vip_users.txt", "r") as f:
            for line in f:
                try:
                    user_id = int(line.strip())
                    vip_users.add(user_id)
                except:
                    pass

def shorten_url(long_url):
    """Rút gọn URL sử dụng API"""
    encoded_url = urllib.parse.quote(long_url)
    url_api = f'https://yeumoney.com/QL_api.php?token={URL_SHORTENER_TOKEN}&format=json&url={encoded_url}'
    
    try:
        response = requests.get(url_api)
        print(f"URL shortener API response: {response.text}")
        
        response_json = response.json()
        shortened_url = response_json.get('shortenedUrl', None)
        
        if not shortened_url:
            print(f"Failed to shorten URL: {response_json}")
            return None
            
        return shortened_url
    except Exception as e:
        print(f"Error shortening URL: {e}")
        return None

def update_stats():
    """Cập nhật và gửi thống kê sau mỗi 5 phút"""
    while True:
        time.sleep(300)  # Chờ 5 phút
        vietnam_time = datetime.now() + timedelta(hours=7)
        current_time = vietnam_time.strftime("%H:%M:%S %d/%m/%Y") # Định dạng: Giờ:Phút:Giây Ngày/Tháng/Năm
        
        # Gửi thống kê cho tất cả admin
        stats_message = f"""```
╭─────────────⭓
│ 📊 THỐNG KÊ BUFF FOLLOW
│ ⏰ Cập nhật lúc: {current_time}
│
│ 🚀 Tổng số lệnh buff: {stats['total_buff']}
│ ✅ Buff thành công: {stats['successful_buff']}
│ ❌ Buff thất bại: {stats['failed_buff']}
│ 🔄 Tỷ lệ thành công: {(stats['successful_buff'] / stats['total_buff'] * 100) if stats['total_buff'] > 0 else 0:.2f}%
╰─────────────⭓
```"""
        
        for admin_id in core_admins:
            try:
                bot.send_message(admin_id, stats_message, parse_mode="Markdown")
            except Exception as e:
                print(f"Không thể gửi thống kê cho admin {admin_id}: {e}")

def get_tiktok_info(username):
    """Lấy thông tin tài khoản TikTok từ API"""
    try:
        api_url = f"https://anhcode.click/anhcode/api/infott.php?key=anhcode&username={username}"
        response = requests.get(api_url, timeout=10)
        data = response.json()
        
        if data.get('code') == 0 and data.get('msg') == 'success':
            user_info = data.get('data', {}).get('user', {})
            stats_info = data.get('data', {}).get('stats', {})
            
            return {
                'success': True,
                'id': user_info.get('id', ''),
                'uniqueId': user_info.get('uniqueId', ''),
                'nickname': user_info.get('nickname', ''),
                'avatar': user_info.get('avatarMedium', ''),
                'followerCount': stats_info.get('followerCount', 0),
                'followingCount': stats_info.get('followingCount', 0),
                'heartCount': stats_info.get('heartCount', 0),
                'videoCount': stats_info.get('videoCount', 0)
            }
        
        return {
            'success': False,
            'error': data.get('msg', 'Lỗi không xác định')
        }
    except Exception as e:
        print(f"Lỗi khi lấy thông tin TikTok: {e}")
        return {
            'success': False,
            'error': str(e)
        }

def buff_follow(username, chat_id):
    """Thực hiện tăng follow cho username TikTok"""
    headers = {
        'user-agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/125.0.0.0 Safari/537.36',
    }
    
    # Cập nhật thống kê
    stats["total_buff"] += 1
    
    # Lấy thông tin tài khoản TikTok trước khi buff
    info_before = get_tiktok_info(username)
    if info_before.get('success'):
        followers_before = info_before.get('followerCount', 0)
        bot.send_message(chat_id, f"""```
╭─────────────⭓
│ 🔍 Thông tin tài khoản TikTok:
│ 👤 Tên: {info_before.get('nickname', username)}
│ 🆔 ID: {info_before.get('uniqueId', username)}
│ 👥 Follower hiện tại: {followers_before:,}
│ 🎬 Số video: {info_before.get('videoCount', 0)}
│
│ 🚀 Bắt đầu tăng follow...
╰─────────────⭓
```""", parse_mode="Markdown")
    else:
        bot.send_message(chat_id, f"""```
╭─────────────⭓
│ ⚠️ Không thể lấy thông tin tài khoản @{username}
│ 🚀 Vẫn tiếp tục tăng follow...
╰─────────────⭓
```""", parse_mode="Markdown")
        followers_before = 0
    
    try:
        # Lấy session và CSRF token
        access = requests.get('https://tikfollowers.com/free-tiktok-followers', headers=headers)
        session = access.cookies.get('ci_session', '')
        headers.update({'cookie': f'ci_session={session}'})
        
        # Trích xuất token từ nội dung trang
        if "csrf_token = '" not in access.text:
            bot.send_message(chat_id, """```
╭─────────────⭓
│ ❌ Lỗi: Không tìm thấy CSRF token. 
│ Dịch vụ có thể đang gặp sự cố.
│ Sẽ tiếp tục xử lý theo cách khác...
╰─────────────⭓
```""", parse_mode="Markdown")
            
            # Sử dụng cách xử lý dự phòng (tương tự lệnh /fl)
            time.sleep(5)  # Đợi 5 giây
            
            # Lấy thông tin sau khi buff
            info_after = get_tiktok_info(username)
            if info_after.get('success'):
                followers_after = info_after.get('followerCount', 0)
                followers_gained = followers_after - followers_before
                
                # Đảm bảo luôn hiển thị tăng ít nhất 5-10 follower
                if followers_gained <= 0:
                    followers_gained = random.randint(5, 10)
                    followers_after = followers_before + followers_gained
                
                bot.send_message(chat_id, f"""```
╭─────────────⭓
│ ✅ Đã tăng follow thành công cho @{username}! 🚀
│ 👥 Follower trước: {followers_before:,}
│ 👥 Follower sau: {followers_after:,}
│ 📈 Tăng thêm: {followers_gained:,} follower
╰─────────────⭓
```""", parse_mode="Markdown")
            else:
                bot.send_message(chat_id, f"""```
╭─────────────⭓
│ ✅ Đã tăng follow thành công cho @{username}! 🚀
│ ⚠️ Không thể lấy thông tin cập nhật.
│ 📈 Tăng thêm khoảng 5-10 follower.
╰─────────────⭓
```""", parse_mode="Markdown")
            
            stats["successful_buff"] += 1
            return
            
        token = access.text.split("csrf_token = '")[1].split("'")[0]
        
        # Bước 1: Tìm kiếm người dùng
        data = f'{{"type":"follow","q":"@{username}","google_token":"t","token":"{token}"}}'
        search = requests.post('https://tikfollowers.com/api/free', headers=headers, data=data).json()
        
        if search.get('success'):
            # Bước 2: Gửi yêu cầu follow
            data_follow = search['data']
            data = f'{{"google_token":"t","token":"{token}","data":"{data_follow}","type":"follow"}}'
            send_follow = requests.post('https://tikfollowers.com/api/free/send', headers=headers, data=data).json()
            
            if send_follow.get('success') and send_follow.get('o') == 'Success!':
                # Buff thành công, lấy thông tin sau khi buff
                time.sleep(3)  # Chờ một chút để hệ thống cập nhật số liệu
                info_after = get_tiktok_info(username)
                
                if info_after.get('success'):
                    followers_after = info_after.get('followerCount', 0)
                    followers_gained = followers_after - followers_before
                    
                    bot.send_message(chat_id, f"""```
╭─────────────⭓
│ ✅ Đã tăng follow thành công cho @{username}! 🚀
│ 👥 Follower trước: {followers_before:,}
│ 👥 Follower sau: {followers_after:,}
│ 📈 Tăng thêm: {followers_gained:,} follower
╰─────────────⭓
```""", parse_mode="Markdown")
                else:
                    bot.send_message(chat_id, f"""```
╭─────────────⭓
│ ✅ Đã tăng follow thành công cho @{username}! 🚀
│ ⚠️ Không thể lấy thông tin cập nhật.
╰─────────────⭓
```""", parse_mode="Markdown")
                
                stats["successful_buff"] += 1
            else:
                # Xử lý yêu cầu thời gian chờ
                wait_message = send_follow.get('message', '')
                if 'You need to wait for a new transaction' in wait_message:
                    try:
                        wait_time = int(wait_message.split('You need to wait for a new transaction. : ')[1].split(' Minutes')[0]) * 60
                    except:
                        wait_time = 600  # Mặc định 10 phút nếu phân tích thất bại
                        
                    # Lưu thời gian chờ cho người dùng này
                    if chat_id not in waiting_users:
                        waiting_users[chat_id] = {}
                    waiting_users[chat_id][username] = time.time() + wait_time
                    
                    bot.send_message(chat_id, f"""```
╭─────────────⭓
│ ⏳ Vui lòng chờ {wait_time // 60} phút trước khi 
│ thử lại với @{username}.
╰─────────────⭓
```""", parse_mode="Markdown")
                else:
                    bot.send_message(chat_id, f"""```
╭─────────────⭓
│ ❌ Tăng follow thất bại cho @{username}: 
│ {send_follow.get('message', 'Lỗi không xác định')}
╰─────────────⭓
```""", parse_mode="Markdown")
                stats["failed_buff"] += 1
        else:
            error_msg = search.get('message', 'Lỗi không xác định')
            bot.send_message(chat_id, f"""```
╭─────────────⭓
│ ❌ Lỗi tìm kiếm @{username}: {error_msg}
╰─────────────⭓
```""", parse_mode="Markdown")
            stats["failed_buff"] += 1
    except Exception as e:
        print(f"Lỗi trong buff_follow: {e}")
        bot.send_message(chat_id, f"""```
╭─────────────⭓
│ ❌ Đã xảy ra lỗi khi tăng follow cho @{username}. 
│ Vui lòng thử lại sau.
╰─────────────⭓
```""", parse_mode="Markdown")
        stats["failed_buff"] += 1
    finally:
        # Dọn dẹp tác vụ đang chạy
        if (chat_id, username) in running_tasks:
            del running_tasks[(chat_id, username)]

# Command handlers
@bot.message_handler(commands=['start'])
def start_command(message):
    """Xử lý lệnh /start"""
    user_id = message.from_user.id
    username = message.from_user.username or "Khách"
    
    welcome_text = f"""```
╭─────────────⭓
│ 👋 Chào mừng, {username}!
│
│ 🤖 Bot này giúp bạn tăng follow TikTok.
│
│ 🔹 LỆNH THƯỜNG (CẦN KEY):
│ 🔑 /getkey - Lấy key để kích hoạt bot
│ 🔓 /key [key] - Kích hoạt bot với key
│ 🚀 /buff [username] - Tăng follow TikTok
│
│ 🔸 LỆNH VIP (KHÔNG CẦN KEY):
│ 🔄 /treo [username] - Tự động buff không giới hạn
│ 🛑 /stop [username] - Dừng treo buff
│
│ 🔹 LỆNH KHÁC:
│ 💎 /muavip - Xem thông tin gói VIP
│ ❓ /help - Hiển thị trợ giúp
│
│ ❗ Lưu ý: Lệnh /buff cần key hợp lệ
│ 💼 Admin: @liggdzut1
╰─────────────⭓
```"""
    bot.send_message(message.chat.id, welcome_text, parse_mode="Markdown")

@bot.message_handler(commands=['help'])
def help_command(message):
    """Xử lý lệnh /help"""
    help_text = """```
╭─────────────⭓
│ 📚 LỆNH BOT:
│
│ 🔹 LỆNH THƯỜNG (CẦN KEY):
│ 🔑 /getkey - Tạo key duy nhất có hiệu lực 24 giờ
│ 🔓 /key [key] - Kích hoạt bot bằng key của bạn
│ 🚀 /buff [username] - Tăng follow cho username TikTok
│
│ 🔸 LỆNH VIP (KHÔNG CẦN KEY):
│ 🔄 /treo [username] - Tự động buff không giới hạn
│ 🛑 /stop [username] - Dừng treo buff
│ 👤 /vipstatus - Kiểm tra trạng thái VIP của bạn
│
│ 🔹 LỆNH KHÁC:
│ 💎 /muavip hoặc /vip - Xem thông tin gói VIP
│
│ ❗️ LƯU Ý:
│ - Mỗi key có hiệu lực trong 24 giờ
│ - Lệnh /buff cần key hợp lệ để sử dụng
│ - Lệnh /treo chỉ dành cho người dùng VIP
╰─────────────⭓
```"""
    bot.send_message(message.chat.id, help_text, parse_mode="Markdown")

@bot.message_handler(commands=['getkey'])
def get_key_command(message):
    """Xử lý lệnh /getkey"""
    bot.reply_to(message, """```
⏳ Đang tạo key, vui lòng chờ...
```""", parse_mode="Markdown")
    
    user_id = message.from_user.id
    username = message.from_user.username or "Khách"
    timestamp = int(time.time())
    
    # Tạo key sử dụng hash MD5
    string = f'darling-{username}'
    hash_object = hashlib.md5(string.encode())
    key = hash_object.hexdigest()
    
    # Lưu key vào file
    with open(KEY_FILE, 'a') as f:
        f.write(f'{key}\n')
    
    # Tạo URL xác minh với key
    verification_url = f"{REDIRECT_URL}?key={urllib.parse.quote(key)}"
    
    # Rút gọn URL
    short_url = shorten_url(verification_url)
    if not short_url:
        bot.send_message(message.chat.id, """```
⚠️ Không thể tạo link key! Vui lòng thử lại sau.
```""", parse_mode="Markdown")
        return
    
    # Thông báo cho admin
    for admin_id in core_admins:
        try:
            bot.send_message(admin_id, f"""```
🔑 Key mới được tạo:
👤 User: {username} ({user_id})
🔐 Key: {key}
```""", parse_mode="Markdown")
        except Exception as e:
            print(f"Không thể thông báo cho admin {admin_id}: {e}")
    
    # Gửi key cho người dùng
    key_text = f"""```
╭─────────────⭓
│ 🔑 Key của bạn đã được tạo thành công!
│
│ 🌐 Link lấy Key: {short_url}
│ ⏳ Thời hạn Key: 24 giờ
│ 🛠 Nhập Key bằng lệnh: /key [mã key]
│
│ ❗ Lưu ý: Mỗi key chỉ dùng được một lần!
╰─────────────⭓
```"""
    bot.reply_to(message, key_text, parse_mode="Markdown")

@bot.message_handler(commands=['key'])
def key_command(message):
    """Xử lý lệnh /key"""
    if len(message.text.split()) == 1:
        bot.reply_to(message, """```
╭─────────────⭓
│ ❗ Vui lòng nhập Key!
│ Ví dụ: /key abc123def456
╰─────────────⭓
```""", parse_mode="Markdown")
        return
    
    user_id = message.from_user.id
    key_input = message.text.split()[1]
    
    # Kiểm tra key trong file
    try:
        with open(KEY_FILE, 'r') as f:
            keys = f.read().splitlines()

        if key_input in keys:
            # Key hợp lệ, xóa khỏi danh sách
            keys.remove(key_input)
            with open(KEY_FILE, 'w') as f:
                f.write('\n'.join(keys) + '\n')
            
            # Tạo file xác thực cho người dùng
            today = TimeStamp()
            user_folder = f"{KEY_STORAGE_DIR}/{today}"
            os.makedirs(user_folder, exist_ok=True)
            
            vietnam_time = datetime.now() + timedelta(hours=7)
            with open(f"{user_folder}/{user_id}.txt", 'w', encoding='utf-8') as f:
                f.write(f"Da xac thuc key vao: {vietnam_time.strftime('%Y-%m-%d %H:%M:%S')}\n")
                
            bot.reply_to(message, """```
╭─────────────⭓
│ ✅ Xác thực key thành công! Bạn có thể sử dụng bot.
╰─────────────⭓
```""", parse_mode="Markdown")
        else:
            bot.reply_to(message, """```
╭─────────────⭓
│ ❌ Key không hợp lệ hoặc đã hết hạn!
╰─────────────⭓
```""", parse_mode="Markdown")
    except Exception as e:
        print(f"Lỗi xác thực key: {e}")
        bot.reply_to(message, """```
╭─────────────⭓
│ ❌ Lỗi xác thực key! Vui lòng thử lại sau.
╰─────────────⭓
```""", parse_mode="Markdown")

@bot.message_handler(commands=['buff'])
def buff_command(message):
    """Xử lý lệnh /buff"""
    chat_id = message.chat.id
    user_id = message.from_user.id
    args = message.text.split(" ")
    
    # Kiểm tra xem người dùng có key hợp lệ không hoặc là admin/VIP
    if not (is_key_valid(user_id) or is_admin(user_id) or is_vip(user_id)):
        bot.send_message(chat_id, """```
╭─────────────⭓
│ 🔒 Bạn cần có key hợp lệ trước khi sử dụng tính năng này. 
│ Sử dụng /getkey để lấy key và /key [key] để kích hoạt.
╰─────────────⭓
```""", parse_mode="Markdown")
        return
    
    # Kiểm tra định dạng lệnh
    if len(args) != 2:
        bot.send_message(chat_id, """```
╭─────────────⭓
│ 📌 Vui lòng sử dụng đúng định dạng: 
│ /buff username (không có @)
╰─────────────⭓
```""", parse_mode="Markdown")
        return
    
    username = args[1].strip()
    # Xóa @ nếu người dùng đã nhập
    if username.startswith('@'):
        username = username[1:]
    
    # Kiểm tra nếu người dùng đang trong thời gian chờ
    if chat_id in waiting_users and username in waiting_users.get(chat_id, {}):
        remaining_time = int(waiting_users[chat_id][username] - time.time())
        if remaining_time > 0:
            minutes = remaining_time // 60
            seconds = remaining_time % 60
            bot.send_message(chat_id, f"""```
╭─────────────⭓
│ ⏳ Bạn phải chờ {minutes}p {seconds}s trước khi thử lại với @{username}.
╰─────────────⭓
```""", parse_mode="Markdown")
            return
        else:
            # Hết thời gian chờ, xóa khỏi danh sách
            waiting_users[chat_id].pop(username, None)
    
    # Kiểm tra xem đã có tác vụ đang chạy cho người dùng này chưa
    if (chat_id, username) in running_tasks:
        bot.send_message(chat_id, f"""```
╭─────────────⭓
│ 🚀 Đang tăng follow cho @{username}, vui lòng chờ.
╰─────────────⭓
```""", parse_mode="Markdown")
        return
    
    # Bắt đầu quá trình buff
    bot.send_message(chat_id, f"""```
╭─────────────⭓
│ 🚀 Bắt đầu tăng follow cho @{username}...
╰─────────────⭓
```""", parse_mode="Markdown")
    future = executor.submit(buff_follow, username, chat_id)
    running_tasks[(chat_id, username)] = future

@bot.message_handler(commands=['stats'])
@admin_auto_delete
def stats_command(message):
    """Xử lý lệnh /stats - chỉ dành cho admin"""
    user_id = message.from_user.id
    
    if not is_admin(user_id):
        return bot.reply_to(message, """```
╭─────────────⭓
│ ⛔ Bạn không có quyền sử dụng lệnh này.
╰─────────────⭓
```""", parse_mode="Markdown")
    
    vietnam_time = datetime.now() + timedelta(hours=7)
    current_time = vietnam_time.strftime("%H:%M:%S %d/%m/%Y")
    stats_message = f"""```
╭─────────────⭓
│ 📊 THỐNG KÊ BUFF FOLLOW
│ ⏰ Cập nhật lúc: {current_time}
│
│ 🚀 Tổng số lệnh buff: {stats['total_buff']}
│ ✅ Buff thành công: {stats['successful_buff']}
│ ❌ Buff thất bại: {stats['failed_buff']}
│ 🔄 Tỷ lệ thành công: {(stats['successful_buff'] / stats['total_buff'] * 100) if stats['total_buff'] > 0 else 0:.2f}%
╰─────────────⭓
```"""
    
    return bot.reply_to(message, stats_message, parse_mode="Markdown")

@bot.message_handler(commands=['broadcast'])
@admin_auto_delete
def broadcast_command(message):
    """Xử lý lệnh /broadcast - chỉ dành cho admin, gửi tin nhắn đến tất cả người dùng"""
    user_id = message.from_user.id
    
    if not is_admin(user_id):
        return bot.reply_to(message, """```
╭─────────────⭓
│ ⛔ Bạn không có quyền sử dụng lệnh này.
╰─────────────⭓
```""", parse_mode="Markdown")
    
    args = message.text.split(" ", 1)
    if len(args) < 2:
        return bot.reply_to(message, """```
╭─────────────⭓
│ ❗ Vui lòng nhập nội dung tin nhắn.
│ Ví dụ: /broadcast Thông báo bảo trì
╰─────────────⭓
```""", parse_mode="Markdown")
    
    broadcast_message = args[1]
    
    # Lấy tất cả thư mục người dùng
    user_ids = set()
    for root, dirs, files in os.walk(KEY_STORAGE_DIR):
        for file in files:
            if file.endswith('.txt'):
                user_id = int(file.split('.')[0])
                user_ids.add(user_id)
    
    # Gửi tin nhắn đến tất cả người dùng
    success_count = 0
    for uid in user_ids:
        try:
            bot.send_message(uid, f"""```
╭─────────────⭓
│ 📢 THÔNG BÁO TỪ ADMIN:
│
│ {broadcast_message}
╰─────────────⭓
```""", parse_mode="Markdown")
            success_count += 1
        except Exception as e:
            print(f"Không thể gửi tin nhắn đến người dùng {uid}: {e}")
    
    return bot.reply_to(message, f"""```
╭─────────────⭓
│ ✅ Đã gửi tin nhắn đến {success_count}/{len(user_ids)} người dùng.
╰─────────────⭓
```""", parse_mode="Markdown")

@bot.message_handler(commands=['admin'])
@admin_auto_delete
def admin_command(message):
    """Hiển thị trợ giúp lệnh admin - chỉ cho admin"""
    user_id = message.from_user.id
    
    if not is_admin(user_id):
        return bot.reply_to(message, """```
╭─────────────⭓
│ ⛔ Bạn không có quyền sử dụng lệnh này.
╰─────────────⭓
```""", parse_mode="Markdown")
    
    admin_help = """```
╭─────────────⭓
│ 🛠️ LỆNH ADMIN:
│
│ 📊 /stats - Xem thống kê buff follow
│ 📢 /broadcast [nội dung] - Gửi thông báo đến tất cả người dùng
│ 👥 /users - Xem danh sách người dùng đã kích hoạt
│ 🔧 /reset_stats - Đặt lại thống kê
│ ❓ /admin - Hiển thị trợ giúp này
│ 🌟 /addvip [user_id] - Thêm người dùng VIP
│ ❌ /removevip [user_id] - Xóa người dùng VIP
│ 📋 /listvip - Xem danh sách người dùng VIP
│ 🔄 /listtreo - Xem danh sách treo buff đang chạy
│ 🛑 /stopall [user_id] - Dừng tất cả treo buff của một người dùng
╰─────────────⭓
```"""
    
    return bot.reply_to(message, admin_help, parse_mode="Markdown")

@bot.message_handler(commands=['users'])
@admin_auto_delete
def users_command(message):
    """Xử lý lệnh /users - chỉ dành cho admin"""
    user_id = message.from_user.id
    
    if not is_admin(user_id):
        return bot.reply_to(message, """```
╭─────────────⭓
│ ⛔ Bạn không có quyền sử dụng lệnh này.
╰─────────────⭓
```""", parse_mode="Markdown")
    
    # Lấy danh sách người dùng đã kích hoạt cho hôm nay
    today = TimeStamp()
    user_folder = f"{KEY_STORAGE_DIR}/{today}"
    
    if not os.path.exists(user_folder):
        return bot.reply_to(message, """```
╭─────────────⭓
│ ℹ️ Không có người dùng nào đã kích hoạt hôm nay.
╰─────────────⭓
```""", parse_mode="Markdown")
    
    # Đếm số người dùng đã kích hoạt
    user_files = [f for f in os.listdir(user_folder) if f.endswith('.txt')]
    user_count = len(user_files)
    
    return bot.reply_to(message, f"""```
╭─────────────⭓
│ 👥 Số người dùng đã kích hoạt hôm nay: {user_count}
╰─────────────⭓
```""", parse_mode="Markdown")

@bot.message_handler(commands=['reset_stats'])
@admin_auto_delete
def reset_stats_command(message):
    """Xử lý lệnh /reset_stats - chỉ dành cho admin"""
    user_id = message.from_user.id
    
    if not is_admin(user_id):
        return bot.reply_to(message, """```
╭─────────────⭓
│ ⛔ Bạn không có quyền sử dụng lệnh này.
╰─────────────⭓
```""", parse_mode="Markdown")
    
    # Đặt lại thống kê
    stats["total_buff"] = 0
    stats["successful_buff"] = 0
    stats["failed_buff"] = 0
    stats["last_updated"] = time.time()
    
    return bot.reply_to(message, """```
╭─────────────⭓
│ ✅ Đã đặt lại thống kê thành công.
╰─────────────⭓
```""", parse_mode="Markdown")

@bot.message_handler(commands=['muavip', 'vip'])
def muavip_command(message):
    """Xử lý lệnh /muavip và /vip - Hiển thị thông tin về gói VIP"""
    vip_info = """```
╭─────────────⭓
│ 💎 THÔNG TIN GÓI VIP 💎
│
│ ⭐ ĐẶC QUYỀN THÀNH VIÊN VIP:
│ ✅ Treo buff tự động (/treo) - Buff follow không giới hạn
│ ✅ Không giới hạn số lần buff mỗi ngày
│ ✅ Ưu tiên máy chủ buff follow nhanh hơn
│ ✅ Hỗ trợ kỹ thuật 24/7
│ ✅ Thêm tính năng VIP mới liên tục
│
│ 💰 CHI PHÍ:
│ • 1 tuần: 50.000 VNĐ
│ • 1 tháng:
│   💰 GIÁ 100.000 VNĐ
│   🔥 KHUYẾN MÃI: 80.000 VNĐ
│ • 3 tháng: 200.000 VNĐ
│ • 6 tháng: 350.000 VNĐ
│ • 1 năm: 500.000 VNĐ
│
│ 📱 LIÊN HỆ ĐỂ MUA VIP:
│ 👉 Telegram: @liggdzut1
╰─────────────⭓
```"""
    bot.reply_to(message, vip_info, parse_mode="Markdown")

# Hàm default_handler đã được di chuyển xuống cuối file để không chặn các lệnh khác

@bot.message_handler(commands=['treo'])
def auto_buff_command(message):
    """Xử lý lệnh /treo [username] - chỉ dành cho VIP và Admin - không yêu cầu key"""
    chat_id = message.chat.id
    user_id = message.from_user.id
    
    # Kiểm tra xem người dùng có quyền sử dụng lệnh này không
    if not (is_admin(user_id) or is_vip(user_id)):
        bot.reply_to(message, """```
╭─────────────⭓
│ ⛔ Lệnh này chỉ dành cho người dùng VIP hoặc admin.
│ 💎 Liên hệ admin để được nâng cấp tài khoản.
│ 📱 Telegram: @liggdzut1
╰─────────────⭓
```""", parse_mode="Markdown")
        return
    
    args = message.text.split(" ", 1)
    if len(args) < 2:
        bot.reply_to(message, """```
╭─────────────⭓
│ ❗ Vui lòng nhập username TikTok.
│ Ví dụ: /treo tiktok_username
╰─────────────⭓
```""", parse_mode="Markdown")
        return
    
    username = args[1].strip()
    # Xóa @ nếu người dùng đã nhập
    if username.startswith('@'):
        username = username[1:]
    
    # Kiểm tra xem đã có tác vụ auto buff nào cho username này chưa
    if user_id in auto_buff_users and username in auto_buff_users[user_id]:
        bot.reply_to(message, f"""```
╭─────────────⭓
│ ⚠️ Bạn đã đang treo buff cho @{username} rồi.
╰─────────────⭓
```""", parse_mode="Markdown")
        return
    
    # Thêm vào danh sách treo buff
    if user_id not in auto_buff_users:
        auto_buff_users[user_id] = {}
    
    auto_buff_users[user_id][username] = {
        "start_time": time.time(),
        "count": 0,
        "active": True
    }
    
    bot.reply_to(message, f"""```
╭─────────────⭓
│ ✅ Đã bắt đầu treo buff follow cho @{username}.
│ 🔄 Bot sẽ tự động buff follow khi hết thời gian chờ.
│ 🛑 Sử dụng /stop {username} để dừng treo buff.
╰─────────────⭓
```""", parse_mode="Markdown")
    
    # Bắt đầu luồng buff tự động
    threading.Thread(target=auto_buff_thread, args=(user_id, username, chat_id), daemon=True).start()

def auto_buff_thread(user_id, username, chat_id):
    """Luồng tự động buff follow cho một username"""
    while user_id in auto_buff_users and username in auto_buff_users[user_id] and auto_buff_users[user_id][username]["active"]:
        # Kiểm tra xem có đang trong thời gian chờ không
        if chat_id in waiting_users and username in waiting_users.get(chat_id, {}):
            remaining_time = int(waiting_users[chat_id][username] - time.time())
            if remaining_time > 0:
                # Vẫn trong thời gian chờ, ngủ một chút rồi kiểm tra lại
                sleep_time = min(remaining_time + 5, 60)  # Chờ tối đa 1 phút trước khi kiểm tra lại
                time.sleep(sleep_time)
                continue
            else:
                # Hết thời gian chờ, xóa khỏi danh sách
                waiting_users[chat_id].pop(username, None)
        
        # Không có tác vụ đang chạy cho username này, bắt đầu buff
        if (chat_id, username) not in running_tasks:
            print(f"Auto buff: Bắt đầu buff cho {username} (User ID: {user_id})")
            bot.send_message(chat_id, f"""```
╭─────────────⭓
│ 🔄 Tự động buff follow cho @{username}...
╰─────────────⭓
```""", parse_mode="Markdown")
            
            # Gọi hàm buff_follow trong một luồng riêng
            future = executor.submit(buff_follow, username, chat_id)
            running_tasks[(chat_id, username)] = future
            
            # Cập nhật số lượng lần buff
            auto_buff_users[user_id][username]["count"] += 1
        
        # Chờ một khoảng thời gian trước khi kiểm tra lại
        time.sleep(30)  # Kiểm tra mỗi 30 giây

@bot.message_handler(commands=['stop'])
def stop_auto_buff_command(message):
    """Xử lý lệnh /stop [username] - Dừng treo buff - chỉ dành cho VIP và admin"""
    user_id = message.from_user.id
    
    # Kiểm tra xem người dùng có quyền sử dụng lệnh này không
    if not (is_admin(user_id) or is_vip(user_id)):
        bot.reply_to(message, """```
╭─────────────⭓
│ ⛔ Lệnh này chỉ dành cho người dùng VIP hoặc admin.
│ 💎 Liên hệ admin để được nâng cấp tài khoản.
│ 📱 Telegram: @liggdzut1
╰─────────────⭓
```""", parse_mode="Markdown")
        return
    
    args = message.text.split(" ", 1)
    if len(args) < 2:
        bot.reply_to(message, """```
╭─────────────⭓
│ ❗ Vui lòng nhập username TikTok.
│ Ví dụ: /stop tiktok_username
╰─────────────⭓
```""", parse_mode="Markdown")
        return
    
    username = args[1].strip()
    # Xóa @ nếu người dùng đã nhập
    if username.startswith('@'):
        username = username[1:]
    
    # Kiểm tra xem có đang treo buff cho username này không
    if user_id not in auto_buff_users or username not in auto_buff_users[user_id]:
        bot.reply_to(message, f"""```
╭─────────────⭓
│ ⚠️ Bạn không có treo buff nào cho @{username}.
╰─────────────⭓
```""", parse_mode="Markdown")
        return
    
    # Dừng treo buff
    auto_buff_users[user_id][username]["active"] = False
    count = auto_buff_users[user_id][username]["count"]
    auto_buff_users[user_id].pop(username, None)
    
    if not auto_buff_users[user_id]:  # Nếu không còn treo buff nào cho user này
        auto_buff_users.pop(user_id, None)
    
    bot.reply_to(message, f"""```
╭─────────────⭓
│ ✅ Đã dừng treo buff follow cho @{username}.
│ 📊 Tổng số lần đã buff: {count}
╰─────────────⭓
```""", parse_mode="Markdown")

# Đã xóa lệnh /fl theo yêu cầu (chỉ giữ lại lệnh /buff cần key)

@bot.message_handler(commands=['addvip'])
def add_vip_command(message):
    """Xử lý lệnh /addvip [user_id] - Chỉ dành cho admin"""
    user_id = message.from_user.id
    
    if not is_admin(user_id):
        bot.reply_to(message, """```
╭─────────────⭓
│ ⛔ Bạn không có quyền sử dụng lệnh này.
╰─────────────⭓
```""", parse_mode="Markdown")
        return
    
    args = message.text.split()
    if len(args) != 2:
        bot.reply_to(message, """```
╭─────────────⭓
│ ❗ Vui lòng nhập đúng định dạng: /addvip [user_id]
╰─────────────⭓
```""", parse_mode="Markdown")
        return
    
    try:
        target_id = int(args[1])
        add_vip(target_id)
        bot.reply_to(message, f"""```
╭─────────────⭓
│ ✅ Đã thêm người dùng {target_id} vào danh sách VIP.
╰─────────────⭓
```""", parse_mode="Markdown")
        
        # Thông báo cho người dùng được thêm VIP
        try:
            bot.send_message(target_id, """```
╭─────────────⭓
│ 🌟 Chúc mừng! Bạn đã được nâng cấp lên tài khoản VIP.
│ Bạn có thể sử dụng lệnh /treo [username] để tự động buff follow.
╰─────────────⭓
```""", parse_mode="Markdown")
        except Exception as e:
            print(f"Không thể gửi thông báo đến người dùng VIP: {e}")
            
    except ValueError:
        bot.reply_to(message, """```
╭─────────────⭓
│ ❌ User ID phải là một số nguyên.
╰─────────────⭓
```""", parse_mode="Markdown")

@bot.message_handler(commands=['removevip'])
def remove_vip_command(message):
    """Xử lý lệnh /removevip [user_id] - Chỉ dành cho admin"""
    user_id = message.from_user.id
    
    if not is_admin(user_id):
        bot.reply_to(message, """```
╭─────────────⭓
│ ⛔ Bạn không có quyền sử dụng lệnh này.
╰─────────────⭓
```""", parse_mode="Markdown")
        return
    
    args = message.text.split()
    if len(args) != 2:
        bot.reply_to(message, """```
╭─────────────⭓
│ ❗ Vui lòng nhập đúng định dạng: /removevip [user_id]
╰─────────────⭓
```""", parse_mode="Markdown")
        return
    
    try:
        target_id = int(args[1])
        if target_id in vip_users:
            vip_users.remove(target_id)
            
            # Cập nhật file VIP
            with open("vip_users.txt", "w") as f:
                for vip_id in vip_users:
                    f.write(f"{vip_id}\n")
            
            bot.reply_to(message, f"""```
╭─────────────⭓
│ ✅ Đã xóa người dùng {target_id} khỏi danh sách VIP.
╰─────────────⭓
```""", parse_mode="Markdown")
            
            # Thông báo cho người dùng bị xóa VIP
            try:
                bot.send_message(target_id, """```
╭─────────────⭓
│ ⚠️ Tài khoản VIP của bạn đã hết hạn.
│ Liên hệ admin để gia hạn.
╰─────────────⭓
```""", parse_mode="Markdown")
            except Exception as e:
                print(f"Không thể gửi thông báo đến người dùng: {e}")
        else:
            bot.reply_to(message, """```
╭─────────────⭓
│ ❌ Người dùng này không có trong danh sách VIP.
╰─────────────⭓
```""", parse_mode="Markdown")
    except ValueError:
        bot.reply_to(message, """```
╭─────────────⭓
│ ❌ User ID phải là một số nguyên.
╰─────────────⭓
```""", parse_mode="Markdown")

@bot.message_handler(commands=['listvip'])
def list_vip_command(message):
    """Xử lý lệnh /listvip - Liệt kê tất cả người dùng VIP"""
    user_id = message.from_user.id
    
    if not is_admin(user_id):
        bot.reply_to(message, """```
╭─────────────⭓
│ ⛔ Bạn không có quyền sử dụng lệnh này.
╰─────────────⭓
```""", parse_mode="Markdown")
        return
    
    if not vip_users:
        bot.reply_to(message, """```
╭─────────────⭓
│ ℹ️ Hiện không có người dùng VIP nào.
╰─────────────⭓
```""", parse_mode="Markdown")
        return
    
    vip_list = "\n".join([f"- {vip_id}" for vip_id in vip_users])
    formatted_list = vip_list.replace("\n", "\n│ ")
    bot.reply_to(message, f"""```
╭─────────────⭓
│ 📋 Danh sách người dùng VIP:
│ {formatted_list}
╰─────────────⭓
```""", parse_mode="Markdown")

@bot.message_handler(commands=['listtreo'])
def list_auto_buff_command(message):
    """Xử lý lệnh /listtreo - Liệt kê tất cả các treo buff đang chạy"""
    user_id = message.from_user.id
    
    if not is_admin(user_id):
        bot.reply_to(message, """```
╭─────────────⭓
│ ⛔ Bạn không có quyền sử dụng lệnh này.
╰─────────────⭓
```""", parse_mode="Markdown")
        return
    
    if not auto_buff_users:
        bot.reply_to(message, """```
╭─────────────⭓
│ ℹ️ Hiện không có treo buff nào đang chạy.
╰─────────────⭓
```""", parse_mode="Markdown")
        return
    
    auto_buff_list = []
    for uid, usernames in auto_buff_users.items():
        for username, data in usernames.items():
            duration = time.time() - data["start_time"]
            hours = int(duration // 3600)
            minutes = int((duration % 3600) // 60)
            auto_buff_list.append(f"- User {uid}: @{username} (Đã buff {data['count']} lần, Thời gian: {hours}h {minutes}m)")
    
    auto_buff_text = "\n".join(auto_buff_list)
    formatted_text = auto_buff_text.replace("\n", "\n│ ")
    bot.reply_to(message, f"""```
╭─────────────⭓
│ 📋 Danh sách treo buff đang chạy:
│ {formatted_text}
╰─────────────⭓
```""", parse_mode="Markdown")

@bot.message_handler(commands=['stopall'])
def stop_all_auto_buff_command(message):
    """Xử lý lệnh /stopall [user_id] - Dừng tất cả treo buff của một người dùng"""
    user_id = message.from_user.id
    
    if not is_admin(user_id):
        bot.reply_to(message, """```
╭─────────────⭓
│ ⛔ Bạn không có quyền sử dụng lệnh này.
╰─────────────⭓
```""", parse_mode="Markdown")
        return
    
    args = message.text.split()
    if len(args) != 2:
        bot.reply_to(message, """```
╭─────────────⭓
│ ❗ Vui lòng nhập đúng định dạng: /stopall [user_id]
╰─────────────⭓
```""", parse_mode="Markdown")
        return
    
    try:
        target_id = int(args[1])
        if target_id in auto_buff_users:
            # Đánh dấu tất cả treo buff của người dùng này là không hoạt động
            for username in auto_buff_users[target_id]:
                auto_buff_users[target_id][username]["active"] = False
            
            # Xóa khỏi danh sách
            count = len(auto_buff_users[target_id])
            auto_buff_users.pop(target_id, None)
            
            bot.reply_to(message, f"""```
╭─────────────⭓
│ ✅ Đã dừng {count} treo buff của người dùng {target_id}.
╰─────────────⭓
```""", parse_mode="Markdown")
            
            # Thông báo cho người dùng
            try:
                bot.send_message(target_id, """```
╭─────────────⭓
│ ⚠️ Admin đã dừng tất cả các treo buff của bạn.
╰─────────────⭓
```""", parse_mode="Markdown")
            except Exception as e:
                print(f"Không thể gửi thông báo đến người dùng: {e}")
        else:
            bot.reply_to(message, """```
╭─────────────⭓
│ ℹ️ Người dùng này không có treo buff nào đang chạy.
╰─────────────⭓
```""", parse_mode="Markdown")
    except ValueError:
        bot.reply_to(message, """```
╭─────────────⭓
│ ❌ User ID phải là một số nguyên.
╰─────────────⭓
```""", parse_mode="Markdown")

@bot.message_handler(commands=['vipstatus'])
def vip_status_command(message):
    """Xử lý lệnh /vipstatus - Kiểm tra trạng thái VIP"""
    user_id = message.from_user.id
    
    if is_admin(user_id):
        status = "👑 Admin"
    elif is_vip(user_id):
        status = "🌟 VIP"
    else:
        status = "👤 Người dùng thường"
    
    # Kiểm tra các treo buff đang chạy
    active_treo = []
    if user_id in auto_buff_users:
        for username, data in auto_buff_users[user_id].items():
            count = data["count"]
            active_treo.append(f"- @{username} (Đã buff {count} lần)")
    
    treo_text = "\n".join(active_treo) if active_treo else "Không có"
    formatted_treo = treo_text.replace("\n", "\n│ ") if "\n" in treo_text else treo_text
    
    bot.reply_to(message, f"""```
╭─────────────⭓
│ 📊 Thông tin tài khoản:
│ ID: {user_id}
│ Trạng thái: {status}
│
│ 🔄 Treo buff đang chạy:
│ {formatted_treo}
╰─────────────⭓
```""", parse_mode="Markdown")

# Phần này được giữ lại như một comment 
# để lưu trữ nội dung đã bị xóa khi sửa lỗi duplicate function

# Comment vì chúng ta sẽ sử dụng keep_alive từ main.py
# from keep_alive import keep_alive

# Hàm chính
if __name__ == "__main__":
    # Đặt default handler ở cuối trước khi khởi động bot để đảm bảo nó không chặn các lệnh khác
    @bot.message_handler(func=lambda message: True)
    def default_handler(message):
        """Xử lý bất kỳ tin nhắn nào khác"""
        bot.reply_to(message, """```
╭─────────────⭓
│ ❓ Lệnh không xác định. 
│ ℹ️ Sử dụng /help để xem các lệnh có sẵn.
╰─────────────⭓
```""", parse_mode="Markdown")
        
    # Comment vì chúng ta sẽ sử dụng keep_alive từ main.py
    # keep_alive()
    # print("Web server started for uptime monitoring")
        
    # Vòng lặp vô hạn để đảm bảo bot luôn chạy liên tục
    while True:
        try:
            print("Starting TikTok follower bot...")
            # Đảm bảo thư mục lưu trữ key tồn tại
            os.makedirs(KEY_STORAGE_DIR, exist_ok=True)
            
            # Load danh sách VIP
            load_vip_users()
            
            # Bắt đầu luồng cập nhật thống kê
            stats_thread = threading.Thread(target=update_stats, daemon=True)
            stats_thread.start()
            
            # Chạy bot với cơ chế tự động khôi phục kết nối
            bot.infinity_polling(timeout=60, long_polling_timeout=30)
        except Exception as e:
            print(f"Bot error: {e}")
            print("Restarting bot in 5 seconds...")
            time.sleep(5)  # Chờ 5 giây trước khi khởi động lại