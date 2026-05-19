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

      <div class="flex-1 flex items-center justify-center my-6 bg-gray-200 rounded-2xl border-2 border-dashed border-gray-300 relative overflow-hidden">
        <div v-if="isLoading" class="absolute inset-0 bg-black/50 z-10 flex flex-col items-center justify-center text-white gap-3">
          <div class="w-10 h-10 border-4 border-blue-500 border-t-transparent rounded-full animate-spin"></div>
          <p class="text-sm font-medium">算法正在疯狂处理中...</p>
        </div>

        <div v-if="currentImage" class="relative max-w-full max-h-[70vh] p-4">
          <img :src="currentImage" alt="Preview" class="max-w-full max-h-[65vh] object-contain shadow-lg rounded" />
          <span class="absolute bottom-6 right-6 bg-black/60 text-white text-xs px-2 py-1 rounded">
            当前预览（已实时应用启用的算法）
          </span>
        </div>
        
        <div v-else class="text-center text-gray-400">
          <p class="text-5xl mb-2">📸</p>
          <p>请先上传一张需要校正的图片</p>
        </div>
      </div>

      <div class="flex justify-end bg-white p-4 rounded-xl shadow-sm">
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
          <div class="flex justify-between text-xs text-gray-500">
            <span>校正角度: {{ pipeline.deskew.angle }}°</span>
          </div>
          <input type="range" min="-45" max="45" v-model.number="pipeline.deskew.angle" @change="runPipeline" class="w-full" />
          <div class="flex items-center gap-2">
            <input type="checkbox" id="auto-deskew" v-model="pipeline.deskew.auto" @change="runPipeline" />
            <label id="auto-deskew" class="text-xs text-gray-600">开启智能自动裁切边缘</label>
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
        <div v-if="pipeline.exposure.enabled" class="space-y-3 pt-2 border-t border-dashed">
          <div class="flex justify-between text-xs text-gray-500">
            <span>亮度偏移: {{ pipeline.exposure.brightness }}</span>
          </div>
          <input type="range" min="-100" max="100" v-model.number="pipeline.exposure.brightness" @change="runPipeline" class="w-full" />
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
          </select>
        </div>
      </div>
      
    </div>
  </div>
</template>

<script setup>
import { ref, reactive } from 'vue';

// --- DOM 引用 ---
const fileInput = ref(null);
const API_BASE_URL = 'http://127.0.0.1:8000/api';

// --- 状态管理 ---
const originImage = ref(null);  // 永远保存最初的用户原图
const currentImage = ref(null); // 画布上渲染的当前图片结果
const isLoading = ref(false);   // 控制全局 Loading 状态

// 完整的流水线参数配置
const pipeline = reactive({
  deskew: { enabled: false, angle: 0, auto: true },
  exposure: { enabled: false, brightness: 0 },
  sharpen: { enabled: false, intensity: 0 },
  filter: { enabled: false, type: 'none' }
});

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
};

// --- 核心流转逻辑（策略 A：单步串行驱动） ---
const runPipeline = async () => {
  if (!originImage.value) return;
  
  isLoading.value = true;
  
  try {
    // 每一层处理，都把上一步的结果当作输入输入进去
    let tempImage = originImage.value;

    // 步骤 1: 歪斜校正
    if (pipeline.deskew.enabled) {
      tempImage = await callDeskewApi(tempImage, pipeline.deskew.angle, pipeline.deskew.auto);
    }

    // 步骤 2: 曝光校正
    if (pipeline.exposure.enabled) {
      tempImage = await callExposureApi(tempImage, pipeline.exposure.brightness);
    }

    // 步骤 3: 增强/锐化
    if (pipeline.sharpen.enabled) {
      tempImage = await callSharpenApi(tempImage, pipeline.sharpen.intensity);
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

  const data = await response.json();
  return data.processedImage;
};

const callDeskewApi = async (image, angle, auto) => {
  return postImageApi('/deskew', { image, angle, auto });
};

const callExposureApi = async (image, brightness) => {
  return postImageApi('/exposure', { image, brightness });
};

const callSharpenApi = async (image, intensity) => {
  return postImageApi('/sharpen', { image, intensity });
};

const callFilterApi = async (image, filterType) => {
  return postImageApi('/filter', { image, filterType });
};

// --- 其他辅助操作 ---
const resetEditor = () => {
  if (!originImage.value) return;
  currentImage.value = originImage.value;
  resetPipelineConfig();
};

const resetPipelineConfig = () => {
  pipeline.deskew = { enabled: false, angle: 0, auto: true };
  pipeline.exposure = { enabled: false, brightness: 0 };
  pipeline.sharpen = { enabled: false, intensity: 0 };
  pipeline.filter = { enabled: false, type: 'none' };
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
