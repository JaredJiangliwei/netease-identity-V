import cv2
import numpy as np
import math

def deskew(image: np.ndarray) -> np.ndarray:
    """
    全自动透视纠偏算法（文档/证件扫描仪核心逻辑）。
    
    自动寻找图像中面积最大的四边形轮廓，并将其透视展平。
    如果未检测到明显的四边形，则安全返回原图。
    
    参数:
        image: 输入图像 (numpy.ndarray)
    返回:
        校正并裁剪后的图像 (numpy.ndarray)
    """
    # 1. 预处理：转换为灰度图
    if len(image.shape) == 3:
        gray = cv2.cvtColor(image, cv2.COLOR_BGR2GRAY)
    else:
        gray = image.copy()

    # 2. 预处理：高斯模糊 (平滑图像，减少纸张纹理或噪点对边缘检测的干扰)
    blurred = cv2.GaussianBlur(gray, (5, 5), 0)

    # 3. 边缘检测 (Canny)
    # 参数 75, 200 是经验值，能较好地捕捉高对比度的边界（如桌子上的白纸）
    edged = cv2.Canny(blurred, 75, 200)

    # (可选) 稍微膨胀边缘，帮助闭合一些由于反光导致断开的线段
    kernel = cv2.getStructuringElement(cv2.MORPH_RECT, (3, 3))
    edged = cv2.dilate(edged, kernel, iterations=1)
    edged = cv2.erode(edged, kernel, iterations=1)

    # 4. 寻找轮廓
    # RETR_LIST 提取所有轮廓，CHAIN_APPROX_SIMPLE 压缩直线段，节省内存
    contours, _ = cv2.findContours(edged.copy(), cv2.RETR_LIST, cv2.CHAIN_APPROX_SIMPLE)

    # 5. 按轮廓面积降序排序，只保留前 5 个最大的，过滤掉背景里的小杂物
    contours = sorted(contours, key=cv2.contourArea, reverse=True)[:5]

    screen_cnt = None

    # 6. 遍历寻找拥有 4 个顶点的多边形
    for c in contours:
        # 计算轮廓周长
        peri = cv2.arcLength(c, True)
        # 多边形逼近：0.02 * peri 是精度参数。值越大，拟合出的多边形边数越少。
        approx = cv2.approxPolyDP(c, 0.02 * peri, True)

        # 如果逼近出的多边形正好有 4 个顶点，我们就认为找到了目标！
        if len(approx) == 4:
            screen_cnt = approx.reshape(4, 2)
            break

    # 7. 安全兜底机制
    # 如果背景太乱，或者目标物体边缘不清晰，算法可能找不到四边形。
    # 此时必须直接返回原图，防止后续代码报错阻断流水线。
    if screen_cnt is None:
        return image

    # ================= 以下为透视变换阶段 =================

    # 将自动找到的 4 个点转换为 float32 格式
    src_points = np.array(screen_cnt, dtype="float32")
    
    # 规范化四个顶点的顺序 (左上, 右上, 右下, 左下)
    rect = _order_points(src_points)
    (tl, tr, br, bl) = rect

    # 计算目标图像的尺寸 (长宽取最大值)
    width_a = np.sqrt(((br[0] - bl[0]) ** 2) + ((br[1] - bl[1]) ** 2))
    width_b = np.sqrt(((tr[0] - tl[0]) ** 2) + ((tr[1] - tl[1]) ** 2))
    maxWidth = max(int(width_a), int(width_b))

    height_a = np.sqrt(((tr[0] - br[0]) ** 2) + ((tr[1] - br[1]) ** 2))
    height_b = np.sqrt(((tl[0] - bl[0]) ** 2) + ((tl[1] - bl[1]) ** 2))
    maxHeight = max(int(height_a), int(height_b))

    # 定义目标完美直角的 4 个点
    dst_points = np.array([
        [0, 0],
        [maxWidth - 1, 0],
        [maxWidth - 1, maxHeight - 1],
        [0, maxHeight - 1]
    ], dtype="float32")

    # 8. 计算透视变换矩阵并执行变换
    M = cv2.getPerspectiveTransform(rect, dst_points)
    warped_image = cv2.warpPerspective(image, M, (maxWidth, maxHeight), flags=cv2.INTER_CUBIC)

    return warped_image


def _order_points(pts: np.ndarray) -> np.ndarray:
    """
    内部辅助函数：将任意顺序的四个点重新排列为标准顺序：[左上, 右上, 右下, 左下]。
    """
    rect = np.zeros((4, 2), dtype="float32")
    
    # 左上角的点：x+y 的和最小；右下角的点：x+y 的和最大
    s = pts.sum(axis=1)
    rect[0] = pts[np.argmin(s)]
    rect[2] = pts[np.argmax(s)]

    # 右上角的点：y-x (或近似的 np.diff(x,y) -> y-x) 最小；左下角的点：y-x 最大
    diff = np.diff(pts, axis=1)
    rect[1] = pts[np.argmin(diff)]
    rect[3] = pts[np.argmax(diff)]

    return rect



def rotate_image_with_crop(image, angle):
    """
    旋转图片并自动裁剪出最大的无空白矩形区域
    
    参数:
        image: numpy.ndarray, 输入图像 (灰度图 shape=[H,W] 或 彩色图 shape=[H,W,C])
        angle: float, 旋转角度（度°），顺时针为正
    
    返回:
        rotated_cropped: numpy.ndarray, 旋转并裁剪后的图像，无空白区域
    """
    # 获取图像尺寸和通道数
    if len(image.shape) == 2:
        h, w = image.shape
        channels = 1
    else:
        h, w, channels = image.shape
    
    # 将角度转换为弧度
    angle_rad = math.radians(angle)
    cos_a = abs(math.cos(angle_rad))
    sin_a = abs(math.sin(angle_rad))
    
    # 计算旋转后能容纳的最大内接矩形尺寸
    # 这是旋转后无空白区域的最大矩形
    if w * sin_a <= h * cos_a:
        new_w = w * cos_a - h * sin_a
        new_h = h
    else:
        new_w = w
        new_h = h * cos_a - w * sin_a
    
    new_w = max(1, int(new_w / (cos_a * cos_a - sin_a * sin_a)))
    new_h = max(1, int(new_h / (cos_a * cos_a - sin_a * sin_a)))
    
    # 计算旋转后的完整画布尺寸
    canvas_w = int(h * sin_a + w * cos_a)
    canvas_h = int(h * cos_a + w * sin_a)
    
    # 创建旋转画布
    if channels == 1:
        rotated = np.zeros((canvas_h, canvas_w), dtype=image.dtype)
    else:
        rotated = np.zeros((canvas_h, canvas_w, channels), dtype=image.dtype)
    
    # 计算旋转中心
    cx, cy = w / 2.0, h / 2.0
    new_cx, new_cy = canvas_w / 2.0, canvas_h / 2.0
    
    # 反向映射：对于旋转后图像的每个像素，找到其在原图中的位置
    cos_val = math.cos(angle_rad)
    sin_val = math.sin(angle_rad)
    
    for i in range(canvas_h):
        for j in range(canvas_w):
            # 相对于旋转中心的坐标
            x = j - new_cx
            y = i - new_cy
            
            # 反向旋转到原图坐标
            src_x = x * cos_val + y * sin_val + cx
            src_y = -x * sin_val + y * cos_val + cy
            
            # 取整
            src_x_int = int(round(src_x))
            src_y_int = int(round(src_y))
            
            # 检查是否在原图范围内
            if 0 <= src_x_int < w and 0 <= src_y_int < h:
                if channels == 1:
                    rotated[i, j] = image[src_y_int, src_x_int]
                else:
                    rotated[i, j] = image[src_y_int, src_x_int]
    
    # 裁剪出最大的内接矩形（无空白区域）
    crop_x = (canvas_w - new_w) // 2
    crop_y = (canvas_h - new_h) // 2
    
    if channels == 1:
        cropped = rotated[crop_y:crop_y+new_h, crop_x:crop_x+new_w]
    else:
        cropped = rotated[crop_y:crop_y+new_h, crop_x:crop_x+new_w, :]
    
    return cropped

def rotate_image_fast(image, angle):
    """
    快速版本：使用更简洁的方法计算并裁剪
    
    参数:
        image: numpy.ndarray
        angle: float, 旋转角度（度°）
    
    返回:
        numpy.ndarray, 旋转并裁剪后的图像
    """
    h, w = image.shape[:2]
    
    # 角度转弧度
    angle_rad = math.radians(angle)
    cos_a = math.cos(angle_rad)
    sin_a = math.sin(angle_rad)
    
    # 计算四个角点旋转后的位置
    corners = np.array([
        [0, 0],
        [w, 0],
        [w, h],
        [0, h]
    ])
    
    # 旋转矩阵
    rot_matrix = np.array([
        [cos_a, -sin_a],
        [sin_a, cos_a]
    ])
    
    # 旋转角点
    rotated_corners = np.dot(corners, rot_matrix.T)
    
    # 计算旋转后图像的边界
    min_x = np.min(rotated_corners[:, 0])
    max_x = np.max(rotated_corners[:, 0])
    min_y = np.min(rotated_corners[:, 1])
    max_y = np.max(rotated_corners[:, 1])
    
    new_w = int(np.ceil(max_x - min_x))
    new_h = int(np.ceil(max_y - min_y))
    
    # 创建新图像
    if len(image.shape) == 2:
        rotated = np.zeros((new_h, new_w), dtype=image.dtype)
    else:
        rotated = np.zeros((new_h, new_w, image.shape[2]), dtype=image.dtype)
    
    # 反向映射
    for i in range(new_h):
        for j in range(new_w):
            # 转换到以旋转中心为原点的坐标系
            x = j - new_w/2.0
            y = i - new_h/2.0
            
            # 反向旋转
            src_x = x * cos_a + y * sin_a + w/2.0
            src_y = -x * sin_a + y * cos_a + h/2.0
            
            # 取最近邻
            src_x_int = int(round(src_x))
            src_y_int = int(round(src_y))
            
            if 0 <= src_x_int < w and 0 <= src_y_int < h:
                if len(image.shape) == 2:
                    rotated[i, j] = image[src_y_int, src_x_int]
                else:
                    rotated[i, j] = image[src_y_int, src_x_int]
    
    # 计算最大的内接矩形
    inner_w = int(w * abs(cos_a) + h * abs(sin_a))
    inner_h = int(h * abs(cos_a) + w * abs(sin_a))
    
    # 裁剪掉超出原始图像范围的部分
    # 找到旋转后图像中完全由原图数据填充的最大矩形
    mask = rotated > 0 if len(image.shape) == 2 else np.any(rotated > 0, axis=2)
    
    # 找到非零区域的边界
    rows = np.any(mask, axis=1)
    cols = np.any(mask, axis=0)
    
    if not np.any(rows) or not np.any(cols):
        return rotated
    
    y_min, y_max = np.where(rows)[0][[0, -1]]
    x_min, x_max = np.where(cols)[0][[0, -1]]
    
    # 返回裁剪后的图像
    if len(image.shape) == 2:
        return rotated[y_min:y_max+1, x_min:x_max+1]
    else:
        return rotated[y_min:y_max+1, x_min:x_max+1, :]


# # 使用示例
# if __name__ == '__main__':
#     import matplotlib.pyplot as plt
    
    
    
#     # 旋转30度
#     rotated_img = rotate_image_with_crop(img, 30)
    
#     # 显示结果
#     plt.figure(figsize=(10, 5))
#     plt.subplot(1, 2, 1)
#     plt.imshow(img, cmap='gray' if len(img.shape) == 2 else None)
#     plt.title('Original')
#     plt.axis('off')
    
#     plt.subplot(1, 2, 2)
#     plt.imshow(rotated_img, cmap='gray' if len(img.shape) == 2 else None)
#     plt.title(f'Rotated & Cropped')
#     plt.axis('off')
    
#     plt.show()