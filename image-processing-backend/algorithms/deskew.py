import cv2
import numpy as np

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