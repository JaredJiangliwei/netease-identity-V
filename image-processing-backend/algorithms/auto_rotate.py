import cv2
import numpy as np
import math

# 引入我们上一步写好的无黑边旋转函数

# 注意：雷灿，不知道这个import会不会报错
# 如果不行的话，麻烦把 rotate.py 里的 rotate_image_without_borders 函数复制过来放在这个文件里就行了
# 总之这个要用到旋转功能的函数，必须要能访问rotate.py 里的 rotate_image_without_borders 函数
from rotate import rotate_image_without_borders 

def auto_smart_deskew(image: np.ndarray) -> np.ndarray:
    """
    【对外接口】自适应智能纠偏函数
    
    流程：
    1. 自动分析图片寻找排版基准线。
    2. 如果没有明显线条或不需要旋转，直接返回原图。
    3. 如果需要旋转，调用无黑边旋转算法返回纠正后的图像。
    
    参数:
        image: 输入图像矩阵 (numpy.ndarray)
    返回:
        校正后的图像矩阵 (numpy.ndarray)
    """
    # 1. 测算最优旋转角度
    best_angle = detect_skew_angle(image)
    
    # 2. 如果角度为 0，说明不需要旋转，直接原路返回，节省算力
    if best_angle == 0.0:
        print("💡 智能纠偏: 未检测到明显倾斜，或无明显水平/竖直参考线，跳过旋转。")
        return image
        
    # 3. 执行旋转 (注意：上面计算出的 angle 是线条自身的角度)
    print(f"🔄 智能纠偏: 检测到有效倾斜，正在自动旋转 {best_angle:.2f} 度...")
    corrected_image = rotate_image_without_borders(image, best_angle)
    
    return corrected_image

def detect_skew_angle(image: np.ndarray) -> float:
    #雷灿，这是辅助函数
    """
    智能检测图像的倾斜角度（基于霍夫直线变换）。
    
    规则：
    1. 寻找图像中明显的水平或竖直直线。
    2. 计算这些直线的倾斜误差。
    3. 如果没有检测到足够的有效直线，则返回 0.0。
    """
    h, w = image.shape[:2]
    
    # 1. 动态缩放：为了保证检测速度和参数的鲁棒性，将检测用的图像最长边限制在 1000px 以内
    max_dim = 1000
    if max(h, w) > max_dim:
        scale = max_dim / max(h, w)
        work_img = cv2.resize(image, (int(w * scale), int(h * scale)))
    else:
        work_img = image.copy()

    # 2. 转灰度并提取边缘
    if len(work_img.shape) == 3:
        gray = cv2.cvtColor(work_img, cv2.COLOR_BGR2GRAY)
    else:
        gray = work_img

    # 使用 Canny 提取高频边缘 (50, 150 是比较通用的经验阈值)
    edges = cv2.Canny(gray, 50, 150, apertureSize=3)

    # 3. 霍夫直线变换
    # minLineLength 设为图像最长边的 10%，意味着只看那些跨度较大的“主线条”
    min_line_length = max(work_img.shape) * 0.1
    lines = cv2.HoughLinesP(
        edges, 
        rho=1, 
        theta=np.pi/180, 
        threshold=50, 
        minLineLength=min_line_length, 
        maxLineGap=20
    )

    # 如果连一条线都没检测到（比如纯色背景或者模糊的一团），直接返回 0
    if lines is None:
        return 0.0

    valid_angles = []
    
    # 4. 遍历检测到的所有直线，计算倾斜角
    for line in lines:
        x1, y1, x2, y2 = line[0]
        
        # 避免除以 0 的情况（绝对垂直的线）
        if x1 == x2:
            angle = 90.0
        else:
            angle = math.degrees(math.atan2(y2 - y1, x2 - x1))
        
        # 将角度归一化到表示“歪斜程度”的范围 [-45°, 45°]
        # 比如：88度的竖线，说明图片顺时针歪了2度，我们需要修正的值就是 -2度
        if angle < -45:
            angle += 90
        elif angle > 45:
            angle -= 90
            
        # 我们只采纳那些歪斜程度在 [-15°, 15°] 之间的线条。
        # 如果一条线倾斜了 30 度，它很可能是图片里的斜线图案，而不是因为图片本身放歪了。
        if abs(angle) <= 15.0:
            valid_angles.append(angle)

    # 5. 智能拦截：有效线条数量太少，说明这不是典型的文档/表格/建筑物图片
    # 设定至少需要 3 条有效线来做决断（可根据业务调整）
    if len(valid_angles) < 3:
        return 0.0

    # 6. 计算中位数作为最终角度
    # 中位数(median)比平均值(mean)更抗干扰，即使有几条错乱的线也不会影响大局
    final_angle = float(np.median(valid_angles))
    
    # 如果倾斜角度极小（肉眼几乎看不出），为了保护画质，不作旋转
    if abs(final_angle) < 0.5:
        return 0.0
        
    return final_angle