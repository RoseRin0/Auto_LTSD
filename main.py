# -*- coding: utf-8 -*-
import os
import json
import time
import win32ui
import win32gui
import win32con
import win32api
import numpy as np
from ctypes import windll
from pynput import mouse, keyboard
import win32process
import psutil
import win32print
import ctypes
from datetime import datetime
from PIL import Image
import pytesseract
import cv2
import re

HWND = None

def extract_valid_float(text: str, type: str = 'float'):
    if type == 'float':
        candidates = re.findall(r"\d+\.\d+", text)
        for c in candidates:
            if re.match(r"^\d{1,2}\.\d$", c):
                return c
        return None
    elif type == 'time':
        # 匹配格式为xx:xx:xx的时间，确保前后不跟数字
        candidates = re.findall(r'(?<!\d)(\d{2}:\d{2}:\d{2})(?!\d)', text)
        for c in candidates:
            parts = c.split(':')
            if len(parts) != 3:
                continue
            mm, ss, ff = parts
            if mm.isdigit() and ss.isdigit() and ff.isdigit():
                mm_int = int(mm)
                ss_int = int(ss)
                ff_int = int(ff)
                # 验证分（0-59）、秒（0-59）、毫秒（0-99）
                if (0 <= mm_int <= 59) and (0 <= ss_int <= 59) and (0 <= ff_int <= 99):
                    return (mm_int, ss_int, ff_int)  # 返回整型元组
        return None
        
def preprocess_image_time(img: np.ndarray) -> np.ndarray:
    gray = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY)
    gray = cv2.resize(gray, None, fx=2, fy=2, interpolation=cv2.INTER_CUBIC)
    _, thresh = cv2.threshold(gray, 0, 255, cv2.THRESH_BINARY + cv2.THRESH_OTSU)
    return thresh

# 图像预处理
def preprocess_image(img: np.ndarray) -> np.ndarray:
    gray = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY)
    _, thresh = cv2.threshold(gray, 250, 255, cv2.THRESH_BINARY)
    return thresh

def wait_text_designated_area(targets: str | list[str], timeout: int = 1, region: tuple = None, max_attempts: int = 3, full_text_return: bool = False, img: np.ndarray = None,type: str = "float"):
    pytesseract.pytesseract.tesseract_cmd = r'D:\Tesseract-OCR\tesseract.exe'
    start = datetime.now()
    if isinstance(targets, str):
        targets = [targets]

    attempt_count = 0
    while attempt_count < max_attempts:
        now = datetime.now()
        if (now - start).seconds > timeout:
            return None
        if img is None:
            img = screenshot()
        if img is None:
            time.sleep(0.1)  # 如果截图失败，等待短暂时间再试
            continue

        # 调试输出图像尺寸
        # print(f"Original image size: {img.shape}")

        # 将NumPy数组转换为Pillow图像对象
        img_pil = Image.fromarray(img)

        # 如果提供了具体的坐标区域，则裁剪图像
        if region:
            # 将坐标区域转换为整数
            region = tuple(map(int, region))
            # 调试输出裁剪区域
            # print(f"Cropping region: {region}")
            img_pil = img_pil.crop(region)

        # 将裁剪后的 Pillow 图像对象转换回 NumPy 数组
        img_cropped = np.array(img_pil)

        # 保存裁剪区域的图像用于调试
        # debug_dir = "./ocr_debug"
        # os.makedirs(debug_dir, exist_ok=True)
        # timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        # cv2.imwrite(f"{debug_dir}/{timestamp}_cropped.png", cv2.cvtColor(img_cropped, cv2.COLOR_RGB2BGR))
        if type == 'float':
            custom_config = r'--oem 3 --psm 13 -c tessedit_char_whitelist=0123456789.'
            result = pytesseract.image_to_string(preprocess_image(img_cropped), lang='eng', config=custom_config)
        elif type == 'time':
            custom_config = r'--oem 3 --psm 7 -c tessedit_char_whitelist=0123456789:'
            result = pytesseract.image_to_string(preprocess_image_time(img_cropped), lang='eng', config=custom_config)
        if type == "time":
            # print(f"识别结果：{result}")
            result = result.strip()  # 去除首尾空白字符和换行符
            match = re.fullmatch(r'\d{2}:\d{2}:\d{2}', result)
            if match:
                # print("✅ 识别到有效时间格式")
                pass
            else:
                # print("❌ 无效时间格式")
                result = None

        if full_text_return:
            return result

        for target in targets:
            if target in result:
                return target

        attempt_count += 1
        time.sleep(0.2)  # 每次截图和 OCR 处理之间增加一个短暂的暂停时间

    return None

def get_scale_factor():
    try:
        windll.shcore.SetProcessDpiAwareness(1)  # 设置进程的 DPI 感知
        scale_factor = windll.shcore.GetScaleFactorForDevice(
            0
        )  # 获取主显示器的缩放因子
        return scale_factor / 100  # 返回百分比形式的缩放因子
    except Exception as e:
        print("Error:", e)
        return None
    
def find_window_recursive(class_pattern, title):
    result = []

    def search(hwnd, _):
        try:
            class_name = win32gui.GetClassName(hwnd)
            window_title = win32gui.GetWindowText(hwnd)
            if re.fullmatch(class_pattern, class_name) and window_title == title:
                result.append(hwnd)
        except:
            pass  # 某些窗口可能无权限访问
        return True  # 继续枚举

    def recurse_all_windows():
        def enum(hwnd, _):
            win32gui.EnumChildWindows(hwnd, search, None)
            return True
        win32gui.EnumWindows(enum, None)

    recurse_all_windows()
    return result[0] if result else 0

RebootCount = 0

def get_screen_shot_hwnd():
    global HWND
    if HWND:
        hwnd = HWND
    else:
        hwnd = find_window_recursive(r'Qt\d+QWindowIcon', 'MuMuPlayer')  # 获取窗口句柄
        # if hwnd:
        #     print(f"找到 MuMuPlayer 窗口句柄：{hwnd}，已缓存")
        # else:
        #     print("未找到窗口")
        HWND = hwnd  # 缓存窗口句柄
    left, top, right, bot = win32gui.GetClientRect(hwnd)
    w = right - left
    h = bot - top
    scale_factor = get_scale_factor()
    width_ratio = w / 1920 * scale_factor
    height_ratio = h / 1080 * scale_factor
    real_w = int(w * scale_factor)
    real_h = int(h * scale_factor)
    return hwnd, real_w, real_h

def screenshot(region: tuple = None) -> np.ndarray | None:
    hwnd, real_w, real_h = get_screen_shot_hwnd()
    hwndDC = win32gui.GetWindowDC(hwnd)
    mfcDC = win32ui.CreateDCFromHandle(hwndDC)
    saveDC = mfcDC.CreateCompatibleDC()

    # 根据是否指定区域设置截图范围
    if region:
        left, top, right, bottom = map(int, region)
        width = right - left
        height = bottom - top
    else:
        left = top = 0
        width = real_w
        height = real_h

    saveBitMap = win32ui.CreateBitmap()
    saveBitMap.CreateCompatibleBitmap(mfcDC, width, height)
    saveDC.SelectObject(saveBitMap)

    # 使用BitBlt直接截取指定区域
    try:
        saveDC.BitBlt(
            (0, 0),             # 目标起点
            (width, height),    # 截图尺寸
            mfcDC,              # 源设备上下文
            (left, top),        # 源起点（相对于窗口客户区）
            win32con.SRCCOPY    # 直接复制模式
        )
    except Exception as e:
        print(f"BitBlt截图失败: {e}")
        return None

    # 获取位图数据
    bmpinfo = saveBitMap.GetInfo()
    bmpstr = saveBitMap.GetBitmapBits(True)
    
    # 转换numpy数组
    img = np.frombuffer(bmpstr, dtype=np.uint8)
    img.shape = (bmpinfo['bmHeight'], bmpinfo['bmWidth'], 4)

    # 资源清理
    win32gui.DeleteObject(saveBitMap.GetHandle())
    saveDC.DeleteDC()
    mfcDC.DeleteDC()
    win32gui.ReleaseDC(hwnd, hwndDC)

    return cv2.cvtColor(img, cv2.COLOR_BGRA2RGB)

def check_type(x, y):
    comment = None
    index = None
    if 1177 < y < 1379:
        base_x = 2212
        for i in range(5):
            left = base_x - 290 * i
            right = left + 156
            if left < x < right:
                comment = "release_skill"
                index = i + 1  # 位置1-5
                break
    else:
        comment = None
    return comment, index

def get_pid_by_mouse_pos():
    """获取鼠标位置下的窗口句柄和进程ID"""
    hwnd = win32gui.WindowFromPoint(win32api.GetCursorPos())
    _, pid = win32process.GetWindowThreadProcessId(hwnd)
    return hwnd, pid

def get_system_scale():
    (system_phy_w, system_phy_h), (system_log_w, system_log_h) = get_system_metrics_with_dpi()
    system_scale_w = system_phy_w / system_log_w if system_log_w else 1.0
    system_scale_h = system_phy_h / system_log_h if system_log_h else 1.0
    if system_scale_w != system_scale_h:
        print(f"警告：系统缩放比例不一致，可能导致坐标计算错误,{system_scale_w:.2f} vs {system_scale_h:.2f}")
        system_scale = max(system_scale_w, system_scale_h)
    else:
        system_scale = system_scale_w
    return system_scale

def get_client_rect(hwnd):
    rect = win32gui.GetClientRect(hwnd)
    system_scale = get_system_scale()
    left, top, right, bottom = rect
    left = int(left * system_scale)
    top = int(top * system_scale)
    right = int(right * system_scale)
    bottom = int(bottom * system_scale)

# ================== 窗口查找工具函数 ==================
def find_window_by_title(window_title: str) -> int:
    """
    根据窗口标题查找窗口句柄（支持模糊匹配）
    返回第一个包含指定标题的窗口句柄
    """
    hwnd_list = []
    
    def enum_handler(hwnd, _):
        if win32gui.IsWindowVisible(hwnd):
            title = win32gui.GetWindowText(hwnd)
            if window_title.lower() in title.lower():
                hwnd_list.append(hwnd)
    
    win32gui.EnumWindows(enum_handler, None)
    return hwnd_list[0] if hwnd_list else None

# ================== 后台控制核心类 ==================
class Control:
    def __init__(self, hwnd: int):
        self.hwnd = hwnd
        self.pid = self._get_window_pid(hwnd)  # 新增PID存储
        self.dpi_calculator = DPICalculator(hwnd)
        self._window_rect = None

    def set_characters(self, characters: list):
        """设置角色配置信息"""
        self.characters = characters

    def _get_character_name(self, index: int) -> str:
        """根据位置索引获取角色名称"""
        for char in self.characters:
            if char['index'] == index:
                return char['name']
        return f'未知角色{index}'
    
    def check_type(self, x, y, comment):
        """修改后的点击类型判断"""
        if comment == "release_skill" and 1177 < y < 1379:
            base_x = 2212
            for i in range(5):
                if base_x - 290*i < x < base_x + 156 - 290*i:
                    char_name = self._get_character_name(i+1)
                    print(f"释放 [{char_name}] 的技能") 
                    break
            else:
                print(f"点击坐标：({x}, {y})")
        else:
            print(f"点击坐标：({x}, {y})")

    def _get_window_pid(self, hwnd):
        """获取窗口所属进程PID"""
        _, pid = win32process.GetWindowThreadProcessId(hwnd)
        return pid
        
    def screen_to_client(self, screen_x: int, screen_y: int, rect) -> tuple:
        """考虑DPI的坐标转换"""
        x = screen_x - rect[0]
        y = screen_y - rect[1]
        return x, y
        
    def click(self, x: int, y: int, scale: float = 1.0, comment: str = None):
        self.check_type(x, y, comment)
        self._send_mouse_event(win32con.WM_LBUTTONDOWN, lparam=win32api.MAKELONG(x, y))
        time.sleep(0.01)
        self._send_mouse_event(win32con.WM_LBUTTONUP, lparam=win32api.MAKELONG(x, y))
        
    def _update_window_rect(self):
        """更新窗口坐标信息"""
        self._window_rect = win32gui.GetWindowRect(self.hwnd)
        
    def send_key(self, key: str):
        """发送单个字符"""
        vk_code = ord(key.upper())
        self._send_key_event(win32con.WM_KEYDOWN, vk_code)
        time.sleep(0.05)
        self._send_key_event(win32con.WM_KEYUP, vk_code)
        
    def scroll(self, clicks: int, x: int, y: int):
        """模拟滚轮滚动"""
        lparam = win32api.MAKELONG(x, y)
        wparam = win32api.MAKELONG(0, win32con.WHEEL_DELTA * clicks)
        self._send_mouse_event(win32con.WM_MOUSEWHEEL, lparam, wparam)
        
    def _send_mouse_event(self, msg, lparam, wparam=0):
        win32gui.SendMessage(self.hwnd, msg, wparam, lparam)
        
    def _send_key_event(self, msg, vk_code):
        win32gui.PostMessage(self.hwnd, msg, vk_code, 0)

# ================== 操作录制系统 ==================
class ActionRecorder:
    def __init__(self, control: Control, filename: str, target_hwnd: int, characters: list):
        self.control = control
        self.filename = filename
        self.target_hwnd = target_hwnd
        self.actions = []
        self.characters = characters  # 新增角色信息
        self.start_time = None
        self.mouse_listener = None
        self.keyboard_listener = None
        self.stop_flag = False

    def _record_action(self, action_type, data, scale: float = 1.0, comment: str = None, index: int = None):
        """记录操作到内存"""
        print(f"记录操作：{action_type} - {data}")
        if len(data) == 2:
            x, y = data
            comment = check_type(x,y)

        timestamp = time.time() - self.start_time
        action = {
            'type': action_type,
            'data': data,
            'delay': timestamp,
            'scale': scale,
            'comment': comment
        }
        if index is not None:
            action['index'] = index
        self.actions.append(action)

    def _is_real_related_window(self, hwnd):
        """基于PID的窗口验证（四层验证）"""
        try:
            # 验证1：基础有效性检查
            if hwnd == 0 or not win32gui.IsWindow(hwnd):
                return False

            # 验证2：进程PID比对（核心修改）
            _, target_pid = win32process.GetWindowThreadProcessId(self.control.hwnd)
            _, current_pid = win32process.GetWindowThreadProcessId(hwnd)
            if target_pid != current_pid:
                return False

            return True
            
        except Exception as e:
            print(f"窗口验证异常：{str(e)}")
            return False
        
    def _safe_get_window_handle(self, x, y):
        """安全获取窗口句柄（三级回退机制）"""
        try:
            # 第一级：标准获取方式
            hwnd = win32gui.WindowFromPoint((x, y))
            if hwnd and hwnd != 0:
                return hwnd
                
            # 第二级：使用子窗口探测
            desktop = win32gui.GetDesktopWindow()
            child = win32gui.ChildWindowFromPoint(desktop, (x, y))
            if child and child != 0:
                return win32gui.GetAncestor(child, win32con.GA_ROOT)
                
            # 第三级：直接返回目标窗口（最终保障）
            return self.target_hwnd
        except:
            return self.target_hwnd

    def _on_click(self, x, y, button, pressed):
        """优化后的点击处理"""
        if pressed and button == mouse.Button.left:
            try:
                # 直接获取目标窗口区域
                target_rect = win32gui.GetWindowRect(self.control.hwnd)
                left, top, right, bottom = target_rect
                # 考虑DPI缩放
                system_scale = get_system_scale()
                left = int(left * system_scale)
                top = int(top * system_scale)
                right = int(right * system_scale)
                bottom = int(bottom * system_scale)
                rect = [left, top, right, bottom]
                x_max = right - left
                y_max = bottom - top
                
                # 转换为客户区坐标
                client_x, client_y = self.control.screen_to_client(x, y, rect)
                comment, index = check_type(client_x, client_y)

                if client_x < 0 or client_y < 0 or client_x > x_max or client_y > y_max:
                    print("点击位置超出窗口范围，忽略操作")
                    return

                # 基于PID的深度验证
                clicked_hwnd = self._safe_get_window_handle(x, y)
                if not self._is_real_related_window(clicked_hwnd):
                    print("点击位置不在目标窗口内，忽略操作")
                    return

                if comment:
                    self._record_action('click', (client_x, client_y), system_scale, comment, index)
                else:
                    self._record_action('click', (client_x, client_y), system_scale)
                
            except Exception as e:
                print(f"点击处理异常：{str(e)}")

    def _on_press(self, key):
        try:
            if key == keyboard.Key.scroll_lock:
                print("\n检测到ScrLk键，停止录制...")
                self.stop()
                return
            
            # 只记录目标窗口获得焦点时的按键
            foreground_hwnd = win32gui.GetForegroundWindow()
            if not self._is_real_related_window(foreground_hwnd):
                return

            key_str = key.char.upper()
            self._record_action('key', key_str)
        except AttributeError:
            pass

    def start(self):
        self.start_time = time.time()
        self.stop_flag = False

        # 启动监听器
        self.mouse_listener = mouse.Listener(on_click=self._on_click)
        self.keyboard_listener = keyboard.Listener(on_press=self._on_press)
        
        self.mouse_listener.start()
        self.keyboard_listener.start()
        
        # 等待直到停止标志被设置
        while not self.stop_flag:
            time.sleep(0.1)
        
        # 停止后保存操作
        self._save_actions()

    def stop(self):
        """设置停止标志"""
        self.stop_flag = True
        if self.mouse_listener and self.mouse_listener.is_alive():
            self.mouse_listener.stop()
        if self.keyboard_listener and self.keyboard_listener.is_alive():
            self.keyboard_listener.stop()

    def _save_actions(self):
        """保存操作到文件"""
        if not self.actions:
            print("无操作记录，不保存文件。")
            return

        # 转换时间为相对延迟
        last_delay = 0
        for action in self.actions:
            current_delay = action['delay']
            action['delay'] = current_delay - last_delay
            last_delay = current_delay
        data = {
            "actions": self.actions,
            "characters": self.characters
        }
        try:
            with open(self.filename, 'w', encoding='utf-8') as f:
                json.dump(data, f, ensure_ascii=False, indent=2)
            print(f"已保存 {len(self.actions)} 个操作到 {self.filename}")
        except Exception as e:
            print(f"保存文件时出错: {e}")

# ================== 操作回放系统 ==================            
def check_is_in_instance():
    print("等待进入副本")
    valid_numbers = None
    while valid_numbers is None:
        img = screenshot(region=(2265, 1265, 2335, 1300))  # 直接截取目标区域
        text = wait_text_designated_area("", img=img, full_text_return=True)
        valid_numbers = extract_valid_float(text, type='float')
    # print(f"检测到冷却时间{valid_numbers}，已进入副本")
    print(f"已进入副本")
    valid_numbers = float(valid_numbers)
    return valid_numbers

class SkillReleaseChecker:
    def __init__(self, skill_release_time):
        time_parts = skill_release_time.split(':')
        self.release_total = int(time_parts[0]) * 60000 + int(time_parts[1]) * 1000 + int(time_parts[2])
        self.now_total = 300000
        self.skill_release_end = False
        self.animation_log = True

    def check(self):
        release_flag = False
        while True:
            text = None
            while text is None or text == '':
                img = screenshot(region=(1200, 195, 1365, 240))
                text = wait_text_designated_area("", img=img, full_text_return=True, type='time')
            now_min, now_sec, now_milisec = extract_valid_float(text, type='time')
            lost_time_total = self.now_total
            self.now_total = now_min * 60000 + now_sec * 1000 + now_milisec
            # print(f"{lost_time_total}, {self.now_total}")
            if self.now_total == lost_time_total:
                if self.animation_log:
                    print(f"{now_min}:{now_sec}:{now_milisec} ---- 大招动画开始")
                release_flag = True
                self.animation_log = False
            if lost_time_total != self.now_total and self.now_total <= self.release_total + 30:
                break
        skill_release_end = self.skill_release_end
        if self.skill_release_end:
            pass
        else:
            print(f"{now_min}:{now_sec}:{now_milisec} ---- 释放技能")
            self.skill_release_end = True
        return release_flag, skill_release_end

class ActionReplayer:
    def __init__(self, control: Control):
        self.control = control
        
    def load(self, filename: str) -> tuple:
        """加载操作记录和角色配置"""
        with open(filename, 'r', encoding='utf-8') as f:
            data = json.load(f)
        return data['actions'], data['characters']

    def execute(self, actions: list, characters: list):
        self.control.set_characters(characters)  # 设置角色信息
        start_cooldown = check_is_in_instance()
        start_cooldown = 0
        print(f"等待冷却时间{start_cooldown}")
        time.sleep(start_cooldown)
        for action in actions:
            checker = SkillReleaseChecker(action['release_time'])
            while True:
                if action['release_time']:
                    release_flag = False
                    skill_release_end = False
                    release_flag, skill_release_end = checker.check()
                    if release_flag:
                        break
                elif action['delay'] > 0:
                    print(f"距离下次释放技能，延迟 {action['delay']} 秒")
                    time.sleep(action['delay'])
                    release_flag = True
                if action['type'] == 'click':
                    if skill_release_end:
                        pass
                    else:
                        x, y = action['data']
                        scale = action.get('scale')
                        comment = action.get('comment')
                        self.control.click(x, y, scale, comment)
                elif action['type'] == 'key':
                    self.control.send_key(action['data'])

def validate_window(hwnd) -> bool:
    """验证窗口是否符合条件"""
    # 获取进程信息
    tid, pid = win32process.GetWindowThreadProcessId(hwnd)
    try:
        process = psutil.Process(pid)
        process_name = process.name()
    except psutil.NoSuchProcess:
        return False

    # 获取窗口尺寸
    left, top, right, bottom = win32gui.GetClientRect(hwnd)
    width = right - left
    height = bottom - top
    system_scale = get_system_scale()
    width, height = int(width * system_scale), int(height * system_scale)  # 考虑DPI缩放

    # 筛选条件（示例：Mumu模拟器且宽度>1000）
    return (
        "MuMuPlayer.exe" in process_name and
        width > 1200 and
        height > 700
    )

# ================分辨率适配================
def get_system_metrics_with_dpi():
    """获取考虑DPI缩放的系统分辨率"""
    hdc = win32gui.GetDC(0)
    # 真实物理分辨率
    physical_width = win32print.GetDeviceCaps(hdc, win32con.DESKTOPHORZRES)
    physical_height = win32print.GetDeviceCaps(hdc, win32con.DESKTOPVERTRES)
    # 逻辑分辨率（系统设置的分辨率）
    logical_width = win32api.GetSystemMetrics(0)
    logical_height = win32api.GetSystemMetrics(1)
    win32gui.ReleaseDC(0, hdc)
    
    return (physical_width, physical_height), (logical_width, logical_height)

def get_system_scaling_factor():
    """获取主显示器缩放比例（返回倍数，例如3.0表示300%）"""
    try:
        # Windows 8.1+ 方法
        shcore = ctypes.windll.shcore
        monitor = ctypes.c_void_p(win32api.MonitorFromPoint((0,0)))
        dpi = ctypes.c_uint()
        shcore.GetDpiForMonitor(monitor, 0, ctypes.byref(dpi), ctypes.byref(dpi))
        return dpi.value / 96.0
    except:
        # 兼容旧版Windows的注册表查询
        key = win32api.RegOpenKey(win32con.HKEY_CURRENT_USER,
                                r"Control Panel\Desktop\WindowMetrics")
        appliedDPI = win32api.RegQueryValueEx(key, "AppliedDPI")[0]
        return appliedDPI / 96.0 if appliedDPI else 1.0

def is_dpi_aware_window(hwnd):
    """检查窗口是否支持DPI感知"""
    try:
        process_id = ctypes.c_uint()
        thread_id = ctypes.windll.user32.GetWindowThreadProcessId(hwnd, ctypes.byref(process_id))
        
        # 获取进程DPI感知模式
        PROCESS_DPI_AWARENESS = ctypes.c_int()
        ctypes.windll.shcore.GetProcessDpiAwareness(process_id, ctypes.byref(PROCESS_DPI_AWARENESS))
        
        # 0 = unaware, 1 = system aware, 2 = per monitor aware
        return PROCESS_DPI_AWARENESS.value > 0
    except:
        return False

class DPICalculator:
    def __init__(self, target_hwnd=None):
        self.hwnd = target_hwnd
        self.system_scale = get_system_scaling_factor()
        self.is_dpi_aware = False if not target_hwnd else is_dpi_aware_window(target_hwnd)
        
    def scale_coordinates(self, x, y):
        """根据DPI设置转换坐标"""
        if self.hwnd and self.is_dpi_aware:
            # DPI感知窗口直接使用物理坐标
            return x, y
        else:
            # 非DPI感知窗口需要反向缩放
            return (
                int(x * self.system_scale),
                int(y * self.system_scale)
            )

    def inverse_scale_coordinates(self, x, y):
        """逆向缩放（用于将物理坐标转逻辑坐标）"""
        if self.hwnd and self.is_dpi_aware:
            return x, y
        else:
            return (
                int(x / self.system_scale),
                int(y / self.system_scale)
            )

# ================== 命令行交互界面 ==================
class CommandInterface:
    @staticmethod
    def show_menu():
        """显示交互菜单"""
        print("\n======== LTSD打轴器 ========")
        print("1. 录制操作流程")
        print("2. 回放操作流程")
        print("3. 退出程序")
        return input("请选择操作类型 (1/2/3): ")

    @staticmethod
    def get_script_filename(prompt):
        """获取script目录下的文件名（自动处理路径和扩展名）"""
        while True:
            filename = input(prompt).strip()
            if not filename:
                print("文件名不能为空，请重新输入")
                continue
            
            # 过滤非法字符并提取纯文件名
            clean_name = os.path.basename(filename).split('.')[0]  # 去除已有扩展名
            if not clean_name:
                print("无效的文件名，请重新输入")
                continue
            
            # 构建完整路径
            script_dir = os.path.join(
                os.path.dirname(os.path.abspath(__file__)),  # 当前脚本目录
                'script'
            )
            os.makedirs(script_dir, exist_ok=True)  # 确保目录存在
            return os.path.join(script_dir, f"{clean_name}.json")

    @staticmethod
    def get_filename(prompt):
        """获取文件名输入"""
        while True:
            path = input(prompt).strip()
            if path:
                return path
            print("文件名不能为空，请重新输入")

    @staticmethod
    def wait_for_keys(type='None'):
        if type == 'init':
            """等待用户按下Enter键"""
            print("请保持鼠标在游戏界面内，按下Enter键开始初始化...\n", end='', flush=True)
            with keyboard.Events() as events:
                for event in events:
                    if isinstance(event, keyboard.Events.Press):
                        if event.key == keyboard.Key.enter:
                            hwnd, pid = get_pid_by_mouse_pos()
                            return hwnd, pid
        else:
            print("无效的操作类型，请重新输入")
            return None

def main():
    global HWND
    # 初始化DPI信息
    system_scale = get_system_scale()
    print(f"系统缩放比例：{system_scale:.1f}x")
    if HWND:
        hwnd = HWND
    else:
        hwnd = find_window_recursive(r'Qt\d+QWindowIcon', 'MuMuPlayer')  # 获取窗口句柄
        # print(f"找到 MuMuPlayer 窗口句柄：{hwnd}，已缓存")

    while True:
        choice = CommandInterface.show_menu()
        
        if choice == '3':
            print("程序退出")
            break
            
        if choice not in ('1', '2'):
            print("无效的选项，请重新选择")
            continue

        filename = CommandInterface.get_script_filename("请输入记录/回放名: ")

        hwnd, pid = CommandInterface.wait_for_keys(type = 'init')
        # print(f"选择的窗口：{win32gui.GetWindowText(hwnd)}")
        # print(f"窗口句柄：{hwnd} 进程ID：{pid}")
        control = Control(hwnd)
        if choice == '1':
            # 收集角色信息
            characters = []
            for i in range(1, 6):
                name = input(f"请输入位置{i}的角色名称：")
                characters.append({"index": i, "name": name.strip()})
            control.set_characters(characters)  # 注入角色信息
            # 录制模式
            recorder = ActionRecorder(control, filename, hwnd, characters)
            print(f"开始录制，按ScrLk键停止...")
            recorder.start()
            print(f"已保存 {len(recorder.actions)} 个操作到 {filename}")
            
        elif choice == '2':
            # 回放模式
            try:
                replayer = ActionReplayer(control)
                actions, characters = replayer.load(filename)
                print(f"找到 {len(actions)} 个操作")
                print(f"加载了 {len(characters)} 个角色配置")
                replayer.execute(actions, characters)
                print("操作回放完成！")
            except FileNotFoundError:
                print(f"错误：文件 {filename} 不存在")

if __name__ == '__main__':
    main()