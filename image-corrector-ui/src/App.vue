<template>
  <div class="flex h-screen bg-gray-100 font-sans text-gray-800">
    <div class="flex-1 flex flex-col justify-between p-6">
      <div class="flex justify-between items-center bg-white p-4 rounded-xl shadow-sm">
        <h1 class="text-xl font-bold flex items-center gap-2">
          <span>🎨</span> 图像智能校正工作台
        </h1>
        <div class="flex gap-3">
          <button 
            @click="triggerUpload" 
            class="px-4 py-2 bg-blue-600 hover:bg-blue-700 text-white rounded-lg transition"
          >
            上传新图片
          </button>
          <input 
            type="file" 
            ref="fileInput" 
            @change="handleFileUpload" 
            accept="image/*" 
            class="hidden" 
          />
          <button 
            @click="resetEditor" 
            :disabled="!originImage"
            class="px-4 py-2 bg-gray-200 hover:bg-gray-300 disabled:opacity-50 disabled:cursor-not-allowed rounded-lg transition"
          >
            重置原图
          </button>
        </div>
      </div>

      <div
        class="flex-1 flex items-center justify-center my-6 bg-gray-200 rounded-2xl border-2 border-dashed border-gray-300 relative overflow-hidden"
        :class="{ 'cursor-crosshair': watermarkPanel.enabled }"
        @pointerdown="startWatermarkSelection"
        @pointermove="updateWatermarkSelection"
        @pointerup="finishWatermarkSelection"
        @pointerleave="finishWatermarkSelection"
      >
        <div v-if="isLoading" class="absolute inset-0 bg-black/50 z-10 flex flex-col items-center justify-center text-white gap-3">
          <div class="w-10 h-10 border-4 border-blue-500 border-t-transparent rounded-full animate-spin"></div>
          <p class="text-sm font-medium">算法正在疯狂处理中...</p>
        </div>

        <div v-if="currentImage" ref="previewStageRef" class="relative max-w-full max-h-[70vh] p-4 pt-10">
          <span class="absolute top-1 right-4 bg-white/90 text-gray-700 text-xs px-2.5 py-1 rounded-full shadow-sm border border-gray-200">
            {{ isComparingOriginal ? '原图预览' : '当前预览' }}
          </span>
          <img
            ref="previewImageRef"
            :src="previewImage"
            alt="Preview"
            class="max-w-full max-h-[65vh] object-contain shadow-lg rounded select-none"
            draggable="false"
          />
          <div
            v-if="watermarkSelectionStyle"
            class="absolute border-2 border-red-500 bg-red-500/15 pointer-events-none"
            :style="watermarkSelectionStyle"
          ></div>
        </div>
        
        <div v-else class="text-center text-gray-400">
          <p class="text-5xl mb-2">📸</p>
          <p>请先上传一张需要校正的图片</p>
        </div>
      </div>

      <div class="flex justify-end bg-white p-4 rounded-xl shadow-sm">
        <button
          @pointerdown.prevent="startCompare"
          @pointerup="stopCompare"
          @pointerleave="stopCompare"
          @pointercancel="stopCompare"
          :disabled="!currentImage || isLoading"
          class="mr-3 px-5 py-2.5 bg-gray-800 hover:bg-gray-900 disabled:opacity-50 disabled:cursor-not-allowed text-white font-medium rounded-lg transition"
        >
          按住查看原图
        </button>
        <button 
          @click="downloadResult" 
          :disabled="!currentImage || isLoading"
          class="px-6 py-2.5 bg-green-600 hover:bg-green-700 disabled:opacity-50 disabled:cursor-not-allowed text-white font-medium rounded-lg transition shadow-md shadow-green-600/20"
        >
          保存并下载最终结果
        </button>
      </div>
    </div>

    <div class="w-96 bg-white border-l border-gray-200 p-6 flex flex-col gap-6 overflow-y-auto shadow-2xl">
      <h2 class="text-lg font-bold border-b pb-3">处理流水线 (Pipeline)</h2>

      <div class="border rounded-xl p-4 bg-gray-50/50" :class="{ 'border-blue-500 bg-blue-50/10': pipeline.deskew.enabled }">
        <div class="flex justify-between items-center mb-3">
          <label class="font-semibold flex items-center gap-2">
            <span class="text-sm">1.</span> 歪斜校正
          </label>
          <input type="checkbox" v-model="pipeline.deskew.enabled" @change="runPipeline" :disabled="!originImage" class="w-4 h-4 text-blue-600" />
        </div>
        <div v-if="pipeline.deskew.enabled" class="space-y-3 pt-2 border-t border-dashed">
          <div class="flex items-center gap-2">
            <input type="checkbox" id="auto-deskew" v-model="pipeline.deskew.auto" @change="runPipeline" />
            <label for="auto-deskew" class="text-xs text-gray-600">自动识别旋转角度</label>
          </div>
          <div class="flex items-center gap-2">
            <input type="checkbox" id="crop-deskew" v-model="pipeline.deskew.crop" @change="runPipeline" />
            <label for="crop-deskew" class="text-xs text-gray-600">自动裁剪文档边缘</label>
          </div>
          <div class="grid grid-cols-2 gap-2">
            <label class="flex items-center gap-2 text-xs text-gray-600">
              <input type="checkbox" v-model="pipeline.deskew.mirrorHorizontal" @change="runPipeline" />
              水平镜像
            </label>
            <label class="flex items-center gap-2 text-xs text-gray-600">
              <input type="checkbox" v-model="pipeline.deskew.mirrorVertical" @change="runPipeline" />
              垂直镜像
            </label>
          </div>
          <div class="flex justify-between text-xs text-gray-500">
            <span v-if="pipeline.deskew.auto">
              识别角度: {{ pipeline.deskew.detectedAngle === null ? '等待检测' : `${pipeline.deskew.detectedAngle.toFixed(2)}°` }}
            </span>
            <span v-else>手动旋转: {{ pipeline.deskew.angle }}°</span>
          </div>
          <input
            type="range"
            min="-180"
            max="180"
            step="0.5"
            v-model.number="pipeline.deskew.angle"
            @change="runPipeline"
            :disabled="pipeline.deskew.auto"
            class="w-full disabled:opacity-40"
          />
          <div class="flex gap-2">
            <button
              type="button"
              @click="rotateByQuarterTurn(-90)"
              class="flex-1 px-2 py-1.5 text-xs bg-gray-200 hover:bg-gray-300 rounded"
            >
              左转90°
            </button>
            <button
              type="button"
              @click="rotateByQuarterTurn(90)"
              class="flex-1 px-2 py-1.5 text-xs bg-gray-200 hover:bg-gray-300 rounded"
            >
              右转90°
            </button>
          </div>
        </div>
      </div>

      <div class="border rounded-xl p-4 bg-gray-50/50" :class="{ 'border-blue-500 bg-blue-50/10': pipeline.exposure.enabled }">
        <div class="flex justify-between items-center mb-3">
          <label class="font-semibold flex items-center gap-2">
            <span class="text-sm">2.</span> 曝光校正
          </label>
          <input type="checkbox" v-model="pipeline.exposure.enabled" @change="runPipeline" :disabled="!originImage" class="w-4 h-4 text-blue-600" />
        </div>
        <div v-if="pipeline.exposure.enabled" class="space-y-4 pt-2 border-t border-dashed">

  <!-- Gamma -->
  <div>
    <div class="flex justify-between text-xs text-gray-500">
      <span>
        Gamma 校正:
        {{ pipeline.exposure.gamma.toFixed(2) }}
      </span>
    </div>

    <input
      type="range"
      min="0.1"
      max="3.0"
      step="0.1"
      v-model.number="pipeline.exposure.gamma"
      @change="runPipeline"
      class="w-full"
    />
  </div>

  <!-- Alpha -->
  <div>
    <div class="flex justify-between text-xs text-gray-500">
      <span>
        对比度 Alpha:
        {{ pipeline.exposure.alpha.toFixed(2) }}
      </span>
    </div>

    <input
      type="range"
      min="0.5"
      max="3.0"
      step="0.1"
      v-model.number="pipeline.exposure.alpha"
      @change="runPipeline"
      class="w-full"
    />
  </div>

  <!-- Beta -->
  <div>
    <div class="flex justify-between text-xs text-gray-500">
      <span>
        亮度 Beta:
        {{ pipeline.exposure.beta }}
      </span>
    </div>

    <input
      type="range"
      min="-100"
      max="100"
      step="1"
      v-model.number="pipeline.exposure.beta"
      @change="runPipeline"
      class="w-full"
    />
  </div>

</div>
      </div>

      <div class="border rounded-xl p-4 bg-gray-50/50" :class="{ 'border-blue-500 bg-blue-50/10': pipeline.sharpen.enabled }">
        <div class="flex justify-between items-center mb-3">
          <label class="font-semibold flex items-center gap-2">
            <span class="text-sm">3.</span> 图像增强 & 锐化
          </label>
          <input type="checkbox" v-model="pipeline.sharpen.enabled" @change="runPipeline" :disabled="!originImage" class="w-4 h-4 text-blue-600" />
        </div>
        <div v-if="pipeline.sharpen.enabled" class="space-y-3 pt-2 border-t border-dashed">
          <select v-model="pipeline.sharpen.mode" @change="runPipeline" class="w-full p-2 border rounded-lg text-sm bg-white">
            <option value="unsharp">Unsharp Masking（推荐）</option>
            <option value="laplacian">Laplacian 边缘锐化</option>
            <option value="sobel">Sobel 细节增强</option>
          </select>
          <div class="flex justify-between text-xs text-gray-500">
            <span>锐化强度: {{ pipeline.sharpen.intensity }}%</span>
          </div>
          <input type="range" min="0" max="100" v-model.number="pipeline.sharpen.intensity" @change="runPipeline" class="w-full" />
        </div>
      </div>

      <div class="border rounded-xl p-4 bg-gray-50/50" :class="{ 'border-blue-500 bg-blue-50/10': pipeline.filter.enabled }">
        <div class="flex justify-between items-center mb-3">
          <label class="font-semibold flex items-center gap-2">
            <span class="text-sm">4.</span> 滤镜应用
          </label>
          <input type="checkbox" v-model="pipeline.filter.enabled" @change="runPipeline" :disabled="!originImage" class="w-4 h-4 text-blue-600" />
        </div>
        <div v-if="pipeline.filter.enabled" class="pt-2 border-t border-dashed">
          <select v-model="pipeline.filter.type" @change="runPipeline" class="w-full p-2 border rounded-lg text-sm bg-white">
            <option value="none">原色模式</option>
            <option value="grayscale">黑白文档</option>
            <option value="vintage">复古增强</option>
            <option value="high-contrast">高对比扫描</option>
            <option value="negative">负片反相</option>
            <option value="warm">暖色调</option>
            <option value="cool">冷色调</option>
            <option value="sketch">铅笔素描</option>
          </select>
        </div>
      </div>

      <div class="border rounded-xl p-4 bg-gray-50/50" :class="{ 'border-purple-500 bg-purple-50/10': aiPanel.expanded }">
        <div class="flex justify-between items-center mb-3">
          <label class="font-semibold flex items-center gap-2">
            <span class="text-sm">5.</span> AI 滤镜
            <span class="text-xs font-normal text-purple-600">（需 GPU，单次较慢）</span>
          </label>
          <input type="checkbox" v-model="aiPanel.expanded" @change="onAIToggle" :disabled="!originImage" class="w-4 h-4 text-purple-600" />
        </div>
        <div v-if="aiPanel.expanded" class="pt-2 border-t border-dashed space-y-2">
          <select v-model="aiPanel.style" class="w-full p-2 border rounded-lg text-sm bg-white">
            <option v-for="opt in AI_STYLE_OPTIONS" :key="opt.value" :value="opt.value">{{ opt.label }}</option>
          </select>
          <div>
            <label class="block text-xs text-gray-600 mb-1">风格化强度：{{ aiPanel.strength.toFixed(2) }}</label>
            <input type="range" min="0.30" max="0.90" step="0.02" v-model.number="aiPanel.strength" class="w-full" />
          </div>
          <div class="flex items-center gap-2">
            <label class="text-xs text-gray-600">Seed：</label>
            <input type="number" v-model.number="aiPanel.seed" class="flex-1 p-1 border rounded text-sm" />
          </div>
          <button
            @click="runAIStyle"
            :disabled="!currentImage || isLoading"
            class="w-full px-3 py-2 bg-purple-600 hover:bg-purple-700 disabled:opacity-50 disabled:cursor-not-allowed text-white rounded-lg text-sm font-medium transition"
          >
            {{ isLoading ? '生成中...' : '应用 AI 风格化' }}
          </button>
          <p class="text-xs text-gray-500 leading-relaxed">
            会基于"当前预览"图生成。先调好前 4 步再点上方按钮。GPU 上 ~1s/张，CPU 上 1-3 分钟。
          </p>
        </div>
      </div>

      <div class="border rounded-xl p-4 bg-gray-50/50" :class="{ 'border-red-500 bg-red-50/10': watermarkPanel.enabled }">
        <div class="flex justify-between items-center mb-3">
          <label class="font-semibold flex items-center gap-2">
            <span class="text-sm">6.</span> 去除水印
          </label>
          <input type="checkbox" v-model="watermarkPanel.enabled" :disabled="!currentImage" class="w-4 h-4 text-red-600" />
        </div>
        <div v-if="watermarkPanel.enabled" class="pt-2 border-t border-dashed space-y-3">
          <select v-model="watermarkPanel.type" class="w-full p-2 border rounded-lg text-sm bg-white">
            <option value="white">浅色水印</option>
            <option value="black">深色水印</option>
          </select>
          <div class="text-xs text-gray-500">
            {{ watermarkPanel.rect ? '已框选区域' : '请在图片上拖拽框选水印' }}
          </div>
          <button
            @click="runWatermarkRemove"
            :disabled="!watermarkPanel.rect || isLoading"
            class="w-full px-3 py-2 bg-red-600 hover:bg-red-700 disabled:opacity-50 disabled:cursor-not-allowed text-white rounded-lg text-sm font-medium transition"
          >
            去除选区水印
          </button>
        </div>
      </div>

    </div>
  </div>
</template>

<script setup>
import { computed, onBeforeUnmount, onMounted, ref, reactive } from 'vue';

// --- DOM 引用 ---
const fileInput = ref(null);
const previewStageRef = ref(null);
const previewImageRef = ref(null);
const API_BASE_URL = import.meta.env.VITE_API_BASE_URL || 'http://127.0.0.1:8766/api';

// --- 状态管理 ---
const originImage = ref(null);  // 永远保存最初的用户原图
const currentImage = ref(null); // 画布上渲染的当前图片结果
const isLoading = ref(false);   // 控制全局 Loading 状态
const isComparingOriginal = ref(false);
const previewImage = computed(() => {
  return isComparingOriginal.value && originImage.value ? originImage.value : currentImage.value;
});
const watermarkSelectionStyle = computed(() => {
  if (!watermarkPanel.rect || !previewImageRef.value || !previewStageRef.value) return null;
  const imageRect = previewImageRef.value.getBoundingClientRect();
  const stageRect = previewStageRef.value.getBoundingClientRect();
  return {
    left: `${watermarkPanel.rect.x * imageRect.width + imageRect.left - stageRect.left}px`,
    top: `${watermarkPanel.rect.y * imageRect.height + imageRect.top - stageRect.top}px`,
    width: `${watermarkPanel.rect.w * imageRect.width}px`,
    height: `${watermarkPanel.rect.h * imageRect.height}px`,
  };
});

// 完整的流水线参数配置
const pipeline = reactive({
  deskew: {
    enabled: false,
    angle: 0,
    auto: true,
    crop: false,
    mirrorHorizontal: false,
    mirrorVertical: false,
    detectedAngle: null,
  },
  exposure: { enabled: false, gamma: 1.0, alpha: 1.0, beta: 0 },
  sharpen: { enabled: false, intensity: 0, mode: 'unsharp' },
  filter: { enabled: false, type: 'none' }
});

// AI 风格化（独立于自动流水线，需手动触发）
const aiPanel = reactive({
  expanded: false,
  style: 'webtoon',
  strength: 0.6,
  seed: 42,
  applied: false,  // 是否已经把 AI 效果应用到 currentImage 上
});

const watermarkPanel = reactive({
  enabled: false,
  type: 'white',
  radius: 3,
  rect: null,
  selecting: false,
  startX: 0,
  startY: 0,
});

const AI_STYLE_OPTIONS = [
  { value: 'webtoon',         label: 'Webtoon 漫画' },
  { value: '3d_cartoon',      label: '3D 卡通' },
  { value: 'cyberpunk_anime', label: '赛博朋克' },
];

// --- 上传逻辑 ---
const triggerUpload = () => {
  fileInput.value.click();
};

const handleFileUpload = async (event) => {
  const file = event.target.files[0];
  if (!file) return;

  const imageDataUrl = await fileToDataUrl(file);
  
  // 1. 初始化原图与当前图
  originImage.value = imageDataUrl;
  currentImage.value = imageDataUrl;
  
  // 2. 重置所有流水线开关
  resetPipelineConfig();
  stopCompare();
};

const startCompare = () => {
  if (!originImage.value || !currentImage.value || isLoading.value) return;
  isComparingOriginal.value = true;
};

const stopCompare = () => {
  isComparingOriginal.value = false;
};

const handleCompareKeyDown = (event) => {
  if (event.code !== 'Space' || event.repeat) return;
  const target = event.target;
  const isTyping = target && ['INPUT', 'TEXTAREA', 'SELECT'].includes(target.tagName);
  if (isTyping) return;
  event.preventDefault();
  startCompare();
};

const handleCompareKeyUp = (event) => {
  if (event.code !== 'Space') return;
  event.preventDefault();
  stopCompare();
};

const getWatermarkPoint = (event) => {
  if (!previewImageRef.value) return null;
  const rect = previewImageRef.value.getBoundingClientRect();
  const x = (event.clientX - rect.left) / rect.width;
  const y = (event.clientY - rect.top) / rect.height;
  if (x < 0 || x > 1 || y < 0 || y > 1) return null;
  return {
    x: Math.max(0, Math.min(1, x)),
    y: Math.max(0, Math.min(1, y)),
  };
};

const updateWatermarkRect = (point) => {
  const x1 = Math.min(watermarkPanel.startX, point.x);
  const y1 = Math.min(watermarkPanel.startY, point.y);
  const x2 = Math.max(watermarkPanel.startX, point.x);
  const y2 = Math.max(watermarkPanel.startY, point.y);
  watermarkPanel.rect = {
    x: x1,
    y: y1,
    w: x2 - x1,
    h: y2 - y1,
  };
};

const startWatermarkSelection = (event) => {
  if (!watermarkPanel.enabled || isLoading.value || isComparingOriginal.value) return;
  const point = getWatermarkPoint(event);
  if (!point) return;
  event.preventDefault();
  watermarkPanel.selecting = true;
  watermarkPanel.startX = point.x;
  watermarkPanel.startY = point.y;
  watermarkPanel.rect = { x: point.x, y: point.y, w: 0, h: 0 };
};

const updateWatermarkSelection = (event) => {
  if (!watermarkPanel.selecting) return;
  const point = getWatermarkPoint(event);
  if (!point) return;
  event.preventDefault();
  updateWatermarkRect(point);
};

const finishWatermarkSelection = (event) => {
  if (!watermarkPanel.selecting) return;
  const point = getWatermarkPoint(event);
  if (point) updateWatermarkRect(point);
  watermarkPanel.selecting = false;
  if (watermarkPanel.rect && (watermarkPanel.rect.w < 0.01 || watermarkPanel.rect.h < 0.01)) {
    watermarkPanel.rect = null;
  }
};

const normalizeRotationAngle = (angle) => {
  let normalized = ((angle + 180) % 360 + 360) % 360 - 180;
  return normalized === -180 ? 180 : normalized;
};

const rotateByQuarterTurn = (delta) => {
  if (!originImage.value || isLoading.value) return;
  pipeline.deskew.auto = false;
  pipeline.deskew.angle = normalizeRotationAngle(pipeline.deskew.angle + delta);
  runPipeline();
};

onMounted(() => {
  window.addEventListener('keydown', handleCompareKeyDown);
  window.addEventListener('keyup', handleCompareKeyUp);
});

onBeforeUnmount(() => {
  window.removeEventListener('keydown', handleCompareKeyDown);
  window.removeEventListener('keyup', handleCompareKeyUp);
});

// --- 核心流转逻辑（策略 A：单步串行驱动） ---
const runPipeline = async () => {
  if (!originImage.value) return;
  
  isLoading.value = true;
  
  try {
    // 每一层处理，都把上一步的结果当作输入输入进去
    let tempImage = originImage.value;

    // 步骤 1: 歪斜校正
    if (pipeline.deskew.enabled) {
      if (pipeline.deskew.auto) {
        const result = await callAutoRotateApi(tempImage);
        tempImage = result.processedImage;
        pipeline.deskew.detectedAngle = result.angle;
      } else {
        pipeline.deskew.detectedAngle = null;
        tempImage = await callRotateApi(tempImage, pipeline.deskew.angle);
      }
      if (pipeline.deskew.crop) {
        tempImage = await callDeskewCropApi(tempImage);
      }
      if (pipeline.deskew.mirrorHorizontal || pipeline.deskew.mirrorVertical) {
        tempImage = await callMirrorApi(
          tempImage,
          pipeline.deskew.mirrorHorizontal,
          pipeline.deskew.mirrorVertical
        );
      }
    }

    // 步骤 2: 曝光校正
    if (pipeline.exposure.enabled) {
      tempImage = await callExposureApi(
        tempImage,
        pipeline.exposure.gamma,
        pipeline.exposure.alpha,
        pipeline.exposure.beta
      );
    }

    // 步骤 3: 增强/锐化
    if (pipeline.sharpen.enabled) {
      tempImage = await callSharpenApi(
        tempImage,
        pipeline.sharpen.intensity,
        pipeline.sharpen.mode
      );
    }

    // 步骤 4: 滤镜
    if (pipeline.filter.enabled) {
      tempImage = await callFilterApi(tempImage, pipeline.filter.type);
    }

    // 最终所有开启的步骤都跑完，更新到画布
    currentImage.value = tempImage;
  } catch (error) {
    console.error("图像处理流水线异常:", error);
    alert("处理失败，请检查算法服务接口。");
  } finally {
    isLoading.value = false;
  }
};

// --- 后端 API 接口 ---
const fileToDataUrl = (file) => {
  return new Promise((resolve, reject) => {
    const reader = new FileReader();
    reader.onload = () => resolve(reader.result);
    reader.onerror = reject;
    reader.readAsDataURL(file);
  });
};

const postImageApi = async (path, payload) => {
  const response = await fetch(`${API_BASE_URL}${path}`, {
    method: 'POST',
    headers: {
      'Content-Type': 'application/json'
    },
    body: JSON.stringify(payload)
  });

  if (!response.ok) {
    throw new Error(`接口请求失败: ${response.status}`);
  }

  return response.json();
};

const callRotateApi = async (image, angle) => {
  const data = await postImageApi('/rotate', { image, angle });
  return data.processedImage;
};

const callAutoRotateApi = async (image) => {
  const data = await postImageApi('/auto-rotate', { image });
  return {
    processedImage: data.processedImage,
    angle: Number(data.angle || 0),
  };
};

const callDeskewCropApi = async (image) => {
  const data = await postImageApi('/deskew', { image });
  return data.processedImage;
};

const callMirrorApi = async (image, mirrorHorizontal, mirrorVertical) => {
  let mirrorMode = 'horizontal';
  if (mirrorHorizontal && mirrorVertical) {
    mirrorMode = 'both';
  } else if (mirrorVertical) {
    mirrorMode = 'vertical';
  }
  const data = await postImageApi('/mirror', { image, mirrorMode });
  return data.processedImage;
};

const callExposureApi = async (
  image,
  gamma,
  alpha,
  beta
) => {

  const data = await postImageApi('/exposure', {
    image,
    gamma,
    alpha,
    beta
  });
  return data.processedImage;

};

const callSharpenApi = async (image, intensity, sharpenMode) => {
  const data = await postImageApi('/sharpen', { image, intensity, sharpenMode });
  return data.processedImage;
};

const callWatermarkRemoveApi = async (image) => {
  const rect = watermarkPanel.rect;
  if (!rect || !previewImageRef.value) return image;
  const imageElement = previewImageRef.value;
  const naturalWidth = imageElement.naturalWidth || imageElement.width;
  const naturalHeight = imageElement.naturalHeight || imageElement.height;
  const data = await postImageApi('/watermark-remove', {
    image,
    x: Math.round(rect.x * naturalWidth),
    y: Math.round(rect.y * naturalHeight),
    w: Math.round(rect.w * naturalWidth),
    h: Math.round(rect.h * naturalHeight),
    watermarkType: watermarkPanel.type,
    radius: watermarkPanel.radius,
  });
  return data.processedImage;
};

const callFilterApi = async (image, filterType) => {
  const data = await postImageApi('/filter', { image, filterType });
  return data.processedImage;
};

const runWatermarkRemove = async () => {
  if (!currentImage.value || !watermarkPanel.rect) return;
  stopCompare();
  isLoading.value = true;
  try {
    currentImage.value = await callWatermarkRemoveApi(currentImage.value);
    watermarkPanel.rect = null;
  } catch (error) {
    console.error('去除水印失败:', error);
    alert('去除水印失败，请重新框选水印区域或检查后端服务接口。');
  } finally {
    isLoading.value = false;
  }
};

const runAIStyle = async () => {
  if (!currentImage.value) return;
  isLoading.value = true;
  try {
    const result = await postImageApi('/ai-style', {
      image: currentImage.value,
      aiStyle: aiPanel.style,
      aiStrength: aiPanel.strength,
      aiSeed: aiPanel.seed,
    });
    currentImage.value = result.processedImage;
    aiPanel.applied = true;
  } catch (error) {
    console.error('AI 风格化失败:', error);
    alert('AI 风格化失败。首次运行需下载约 7GB 模型，并请确认已装好 torch + diffusers（见 requirements-ai.txt）。');
  } finally {
    isLoading.value = false;
  }
};

// 取消勾选 AI 滤镜时，如果之前应用过 AI，就回退到前 4 步的结果（重跑流水线）
const onAIToggle = async () => {
  if (!aiPanel.expanded && aiPanel.applied) {
    aiPanel.applied = false;
    await runPipeline();
  }
};

// --- 其他辅助操作 ---
const resetEditor = () => {
  if (!originImage.value) return;
  currentImage.value = originImage.value;
  resetPipelineConfig();
  stopCompare();
};

const resetPipelineConfig = () => {
  pipeline.deskew = {
    enabled: false,
    angle: 0,
    auto: true,
    crop: false,
    mirrorHorizontal: false,
    mirrorVertical: false,
    detectedAngle: null,
  };
  pipeline.exposure = { enabled: false, gamma: 1.0, alpha: 1.0, beta: 0 };
  pipeline.sharpen = { enabled: false, intensity: 0, mode: 'unsharp' };
  pipeline.filter = { enabled: false, type: 'none' };
  aiPanel.expanded = false;
  aiPanel.style = 'webtoon';
  aiPanel.strength = 0.6;
  aiPanel.seed = 42;
  aiPanel.applied = false;
  watermarkPanel.enabled = false;
  watermarkPanel.type = 'white';
  watermarkPanel.radius = 3;
  watermarkPanel.rect = null;
  watermarkPanel.selecting = false;
};

const downloadResult = () => {
  if (!currentImage.value) return;
  const link = document.createElement('a');
  link.href = currentImage.value;
  link.download = `corrected_image_${Date.now()}.png`;
  link.click();
};
</script>

<style scoped>
/* 可以在这里微调滑块或自定义样式，Tailwind 基本上搞定大部分了 */
input[type="range"] {
  accent-color: #2563eb; /* 统一滑块颜色为 Tailwind 的 blue-600 */
}
</style>
