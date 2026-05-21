import cv2
import numpy as np
import math

def rotate_image_without_borders(image: np.ndarray, theta: float) -> np.ndarray:
    """
    对图像进行任意角度的旋转，并自动缩放以消除旋转产生的黑边。
    
    原理说明：
    根据旋转角度计算出最大内接矩形的比例，并将该比例的倒数作为缩放因子（zoom_factor）
    传入仿射变换矩阵中，从而实现一步到位的无损旋转与放大，避免了二次插值带来的画质损失。
    支持全角度 (-180° 到 180°) 的完美等效映射。

    参数:
        image (np.ndarray): 输入的图像矩阵，支持单通道(灰度)或多通道(BGR/RGB)。
        theta (float): 旋转角度，单位为度(°)。正数代表逆时针，负数代表顺时针。取值范围无限制，常用 [-180.0, 180.0]。

    返回:
        np.ndarray: 旋转并自动放大去黑边后的图像矩阵，尺寸(shape)与输入图像完全一致。
    """
    # 1. 获取原图尺寸
    h, w = image.shape[:2]
    
    # 2. 角度转弧度，并利用绝对值处理超过 90 度的翻转情况
    # 超过 90 度时，相当于图像倒置后再进行锐角旋转，绝对值可确保长宽比例计算始终为正
    angle_rad = math.radians(theta)
    cos_a = abs(math.cos(angle_rad))
    sin_a = abs(math.sin(angle_rad))
    
    # 3. 计算在当前角度下，图像为了不留黑边所允许的最小缩放安全比例
    scale_w = w / (w * cos_a + h * sin_a)
    scale_h = h / (w * sin_a + h * cos_a)
    safe_scale = min(scale_w, scale_h)
    
    # 4. 放大倍数即为安全比例的倒数
    zoom_factor = 1.0 / safe_scale
    
    # 5. 获取 2D 旋转仿射矩阵 (中心点, 角度, 缩放比例)
    center = (w / 2, h / 2)
    rotation_matrix = cv2.getRotationMatrix2D(center, theta, zoom_factor)
    
    # 6. 执行仿射变换
    # 使用 INTER_CUBIC (三次插值) 保证放大后的画质
    if len(image.shape) == 2:
        # 单通道灰度图处理
        rotated = cv2.warpAffine(
            image, 
            rotation_matrix, 
            (w, h), 
            flags=cv2.INTER_CUBIC, 
            borderMode=cv2.BORDER_CONSTANT, 
            borderValue=0
        )
    else:
        # 多通道彩色图处理
        rotated = cv2.warpAffine(
            image, 
            rotation_matrix, 
            (w, h), 
            flags=cv2.INTER_CUBIC, 
            borderMode=cv2.BORDER_CONSTANT, 
            borderValue=(0, 0, 0)
        )
        
    return rotated

# ================= 测试代码  =================
# if __name__ == "__main__":
#     dummy_image = np.ones((500, 800, 3), dtype=np.uint8) * 255
#     result = rotate_image_without_borders(dummy_image, 45.0)
#     print(f"原图尺寸: {dummy_image.shape}, 旋转后尺寸: {result.shape}")
#     pass