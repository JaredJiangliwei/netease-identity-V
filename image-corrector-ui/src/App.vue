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
          <canvas
            v-if="brushPanel.enabled"
            ref="brushCanvasRef"
            class="max-w-full max-h-[65vh] object-contain shadow-lg rounded select-none cursor-crosshair"
            @pointerdown.stop="onBrushDown"
            @pointermove.stop="onBrushMove"
            @pointerup.stop="onBrushUp"
            @pointerleave.stop="onBrushUp"
            @pointercancel.stop="onBrushUp"
          ></canvas>
          <img
            v-else
            ref="previewImageRef"
            :src="previewImage"
            alt="Preview"
            class="max-w-full max-h-[65vh] object-contain shadow-lg rounded select-none"
            draggable="false"
          />
          <div
            v-if="watermarkSelectionStyle && !brushPanel.enabled"
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

      <div class="border rounded-xl p-4 bg-gray-50/50" :class="{ 'border-blue-500 bg-blue-50/10': pipeline.wiener.enabled }">
        <div class="flex justify-between items-center mb-3">
          <label class="font-semibold flex items-center gap-2">
            <span class="text-sm">4.</span> 运动模糊修复
          </label>
          <input type="checkbox" v-model="pipeline.wiener.enabled" @change="runPipeline" :disabled="!originImage" class="w-4 h-4 text-blue-600" />
        </div>
        <div v-if="pipeline.wiener.enabled" class="space-y-3 pt-2 border-t border-dashed">
          <label class="flex items-center gap-2 text-xs text-gray-600">
            <input type="radio" value="auto" v-model="pipeline.wiener.mode" @change="runPipeline" />
            自动修复（推荐）
          </label>
          <label class="flex items-center gap-2 text-xs text-gray-600">
            <input type="radio" value="manual" v-model="pipeline.wiener.mode" @change="runPipeline" />
            高级调参
          </label>
          <div v-if="pipeline.wiener.mode === 'auto'" class="text-xs text-gray-500 leading-relaxed">
            {{ pipeline.wiener.autoResult || '自动尝试多组运动方向和长度，并选择较稳的修复结果。' }}
          </div>
          <div v-if="pipeline.wiener.mode === 'manual'">
            <div class="flex justify-between text-xs text-gray-500">
              <span>模糊长度: {{ pipeline.wiener.length }} px</span>
            </div>
            <input type="range" min="1" max="60" step="1" v-model.number="pipeline.wiener.length" @change="runPipeline" class="w-full" />
          </div>
          <div v-if="pipeline.wiener.mode === 'manual'">
            <div class="flex justify-between text-xs text-gray-500">
              <span>运动角度: {{ pipeline.wiener.angle }}°</span>
            </div>
            <input type="range" min="-180" max="180" step="1" v-model.number="pipeline.wiener.angle" @change="runPipeline" class="w-full" />
          </div>
          <div v-if="pipeline.wiener.mode === 'manual'">
            <div class="flex justify-between text-xs text-gray-500">
              <span>噪声抑制: {{ pipeline.wiener.noise.toFixed(3) }}</span>
            </div>
            <input type="range" min="0.001" max="0.080" step="0.001" v-model.number="pipeline.wiener.noise" @change="runPipeline" class="w-full" />
          </div>
        </div>
      </div>

      <div class="border rounded-xl p-4 bg-gray-50/50" :class="{ 'border-blue-500 bg-blue-50/10': pipeline.filter.enabled }">
        <div class="flex justify-between items-center mb-3">
          <label class="font-semibold flex items-center gap-2">
            <span class="text-sm">5.</span> 滤镜应用
          </label>
          <input type="checkbox" v-model="pipeline.filter.enabled" @change="runPipeline" :disabled="!originImage" class="w-4 h-4 text-blue-600" />
        </div>
        <div v-if="pipeline.filter.enabled" class="pt-2 border-t border-dashed space-y-3">
          <select v-model="pipeline.filter.type" @change="runPipeline" class="w-full p-2 border rounded-lg text-sm bg-white">
            <option value="none">原色模式</option>
            <option value="grayscale">黑白文档</option>
            <option value="vintage">复古增强 (sepia)</option>
            <option value="high-contrast">高对比扫描</option>
            <option value="negative">负片反相</option>
            <option value="warm">暖色调</option>
            <option value="cool">冷色调</option>
            <option value="sketch">铅笔素描</option>
            <option value="emboss">浮雕 (emboss)</option>
            <option value="mosaic">马赛克 (mosaic)</option>
            <option value="vignette">晕影 (vignette)</option>
            <option value="motion_blur">运动模糊 (motion blur)</option>
          </select>

          <!-- vintage / sepia -->
          <div v-if="pipeline.filter.type === 'vintage'" class="space-y-1">
            <div class="flex justify-between text-xs text-gray-600">
              <span>怀旧强度</span><span>{{ pipeline.filter.params.vintage.strength.toFixed(2) }}</span>
            </div>
            <input type="range" min="0" max="1.5" step="0.05" v-model.number="pipeline.filter.params.vintage.strength" @change="runPipeline" class="w-full" />
            <div class="text-right pt-1">
              <button type="button" @click="resetFilterParams('vintage')" class="text-xs text-gray-500 hover:text-blue-600 underline">↺ 恢复默认</button>
            </div>
          </div>

          <!-- high-contrast -->
          <div v-if="pipeline.filter.type === 'high-contrast'" class="space-y-2">
            <div class="space-y-1">
              <div class="flex justify-between text-xs text-gray-600">
                <span>对比度 alpha</span><span>{{ pipeline.filter.params.highContrast.alpha.toFixed(2) }}</span>
              </div>
              <input type="range" min="0.5" max="3.0" step="0.05" v-model.number="pipeline.filter.params.highContrast.alpha" @change="runPipeline" class="w-full" />
            </div>
            <div class="space-y-1">
              <div class="flex justify-between text-xs text-gray-600">
                <span>亮度 beta</span><span>{{ pipeline.filter.params.highContrast.beta }}</span>
              </div>
              <input type="range" min="-50" max="50" step="1" v-model.number="pipeline.filter.params.highContrast.beta" @change="runPipeline" class="w-full" />
            </div>
            <div class="text-right pt-1">
              <button type="button" @click="resetFilterParams('highContrast')" class="text-xs text-gray-500 hover:text-blue-600 underline">↺ 恢复默认</button>
            </div>
          </div>

          <!-- warm -->
          <div v-if="pipeline.filter.type === 'warm'" class="space-y-1">
            <div class="flex justify-between text-xs text-gray-600">
              <span>暖度</span><span>{{ pipeline.filter.params.warm.strength.toFixed(2) }}</span>
            </div>
            <input type="range" min="0" max="2" step="0.05" v-model.number="pipeline.filter.params.warm.strength" @change="runPipeline" class="w-full" />
            <div class="text-right pt-1">
              <button type="button" @click="resetFilterParams('warm')" class="text-xs text-gray-500 hover:text-blue-600 underline">↺ 恢复默认</button>
            </div>
          </div>

          <!-- cool -->
          <div v-if="pipeline.filter.type === 'cool'" class="space-y-1">
            <div class="flex justify-between text-xs text-gray-600">
              <span>冷度</span><span>{{ pipeline.filter.params.cool.strength.toFixed(2) }}</span>
            </div>
            <input type="range" min="0" max="2" step="0.05" v-model.number="pipeline.filter.params.cool.strength" @change="runPipeline" class="w-full" />
            <div class="text-right pt-1">
              <button type="button" @click="resetFilterParams('cool')" class="text-xs text-gray-500 hover:text-blue-600 underline">↺ 恢复默认</button>
            </div>
          </div>

          <!-- sketch -->
          <div v-if="pipeline.filter.type === 'sketch'" class="space-y-2">
            <div class="space-y-1">
              <div class="flex justify-between text-xs text-gray-600">
                <span>模糊核大小</span><span>{{ pipeline.filter.params.sketch.blurKsize }}</span>
              </div>
              <input type="range" min="3" max="99" step="2" v-model.number="pipeline.filter.params.sketch.blurKsize" @change="runPipeline" class="w-full" />
            </div>
            <div class="space-y-1">
              <div class="flex justify-between text-xs text-gray-600">
                <span>线条强度</span><span>{{ pipeline.filter.params.sketch.strength.toFixed(2) }}</span>
              </div>
              <input type="range" min="0.3" max="1.6" step="0.02" v-model.number="pipeline.filter.params.sketch.strength" @change="runPipeline" class="w-full" />
            </div>
            <div class="text-right pt-1">
              <button type="button" @click="resetFilterParams('sketch')" class="text-xs text-gray-500 hover:text-blue-600 underline">↺ 恢复默认</button>
            </div>
          </div>

          <!-- emboss -->
          <div v-if="pipeline.filter.type === 'emboss'" class="space-y-2">
            <div class="space-y-1">
              <span class="text-xs text-gray-600">光照方向</span>
              <select v-model="pipeline.filter.params.emboss.direction" @change="runPipeline" class="w-full p-1.5 border rounded text-sm bg-white">
                <option v-for="d in ['NW','N','NE','E','SE','S','SW','W']" :key="d" :value="d">{{ d }}</option>
              </select>
            </div>
            <div class="space-y-1">
              <div class="flex justify-between text-xs text-gray-600">
                <span>强度</span><span>{{ pipeline.filter.params.emboss.strength.toFixed(2) }}</span>
              </div>
              <input type="range" min="0.2" max="3" step="0.1" v-model.number="pipeline.filter.params.emboss.strength" @change="runPipeline" class="w-full" />
            </div>
            <label class="flex items-center gap-2 text-xs text-gray-600">
              <input type="checkbox" v-model="pipeline.filter.params.emboss.mono" @change="runPipeline" />
              灰度输出
            </label>
            <div class="text-right pt-1">
              <button type="button" @click="resetFilterParams('emboss')" class="text-xs text-gray-500 hover:text-blue-600 underline">↺ 恢复默认</button>
            </div>
          </div>

          <!-- mosaic -->
          <div v-if="pipeline.filter.type === 'mosaic'" class="space-y-1">
            <div class="flex justify-between text-xs text-gray-600">
              <span>块大小 (像素)</span><span>{{ pipeline.filter.params.mosaic.block }}</span>
            </div>
            <input type="range" min="2" max="80" step="1" v-model.number="pipeline.filter.params.mosaic.block" @change="runPipeline" class="w-full" />
            <div class="text-right pt-1">
              <button type="button" @click="resetFilterParams('mosaic')" class="text-xs text-gray-500 hover:text-blue-600 underline">↺ 恢复默认</button>
            </div>
          </div>

          <!-- vignette -->
          <div v-if="pipeline.filter.type === 'vignette'" class="space-y-2">
            <div class="space-y-1">
              <div class="flex justify-between text-xs text-gray-600">
                <span>亮区半径</span><span>{{ pipeline.filter.params.vignette.sigmaScale.toFixed(2) }}</span>
              </div>
              <input type="range" min="0.1" max="1.5" step="0.05" v-model.number="pipeline.filter.params.vignette.sigmaScale" @change="runPipeline" class="w-full" />
            </div>
            <div class="space-y-1">
              <div class="flex justify-between text-xs text-gray-600">
                <span>边角暗度</span><span>{{ pipeline.filter.params.vignette.darkness.toFixed(2) }}</span>
              </div>
              <input type="range" min="0" max="1" step="0.05" v-model.number="pipeline.filter.params.vignette.darkness" @change="runPipeline" class="w-full" />
            </div>
            <div class="grid grid-cols-2 gap-2">
              <div class="space-y-1">
                <div class="flex justify-between text-xs text-gray-600">
                  <span>中心 X</span><span>{{ pipeline.filter.params.vignette.centerX.toFixed(2) }}</span>
                </div>
                <input type="range" min="0" max="1" step="0.02" v-model.number="pipeline.filter.params.vignette.centerX" @change="runPipeline" class="w-full" />
              </div>
              <div class="space-y-1">
                <div class="flex justify-between text-xs text-gray-600">
                  <span>中心 Y</span><span>{{ pipeline.filter.params.vignette.centerY.toFixed(2) }}</span>
                </div>
                <input type="range" min="0" max="1" step="0.02" v-model.number="pipeline.filter.params.vignette.centerY" @change="runPipeline" class="w-full" />
              </div>
            </div>
            <div class="text-right pt-1">
              <button type="button" @click="resetFilterParams('vignette')" class="text-xs text-gray-500 hover:text-blue-600 underline">↺ 恢复默认</button>
            </div>
          </div>

          <!-- motion_blur -->
          <div v-if="pipeline.filter.type === 'motion_blur'" class="space-y-2">
            <div class="space-y-1">
              <div class="flex justify-between text-xs text-gray-600">
                <span>核长度</span><span>{{ pipeline.filter.params.motionBlur.ksize }}</span>
              </div>
              <input type="range" min="3" max="61" step="2" v-model.number="pipeline.filter.params.motionBlur.ksize" @change="runPipeline" class="w-full" />
            </div>
            <div class="space-y-1">
              <div class="flex justify-between text-xs text-gray-600">
                <span>方向 (度)</span><span>{{ pipeline.filter.params.motionBlur.angle }}°</span>
              </div>
              <input type="range" min="0" max="180" step="5" v-model.number="pipeline.filter.params.motionBlur.angle" @change="runPipeline" class="w-full" />
            </div>
            <div class="text-right pt-1">
              <button type="button" @click="resetFilterParams('motionBlur')" class="text-xs text-gray-500 hover:text-blue-600 underline">↺ 恢复默认</button>
            </div>
          </div>
        </div>
      </div>

      <div class="border rounded-xl p-4 bg-gray-50/50" :class="{ 'border-purple-500 bg-purple-50/10': aiPanel.expanded }">
        <div class="flex justify-between items-center mb-3">
          <label class="font-semibold flex items-center gap-2">
            <span class="text-sm">6.</span> AI 滤镜
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

      <div class="border rounded-xl p-4 bg-gray-50/50" :class="{ 'border-amber-500 bg-amber-50/10': defocusPanel.expanded }">
        <div class="flex justify-between items-center mb-3">
          <label class="font-semibold flex items-center gap-2">
            <span class="text-sm">7.</span> 失焦恢复
            <span class="text-xs font-normal text-amber-600">（CodeFormer 人脸修复,需 GPU）</span>
          </label>
          <input type="checkbox" v-model="defocusPanel.expanded" :disabled="!originImage" class="w-4 h-4 text-amber-600" />
        </div>
        <div v-if="defocusPanel.expanded" class="pt-2 border-t border-dashed space-y-3">
          <div class="text-xs text-gray-600 leading-relaxed">
            CodeFormer 用不同 <code class="px-1 bg-gray-200 rounded text-[10px]">fidelity weight (w)</code> 生成多张候选,w 越小越激进、越清晰但易偏离原貌;w 越大越保真。生成后从下方网格里挑选满意的应用为新底图。
          </div>
          <div>
            <label class="block text-xs text-gray-600 mb-1">候选 w 值(逗号分隔,0~1)</label>
            <input type="text" v-model="defocusPanel.weightsText" placeholder="0.3, 0.4, 0.5, 0.6"
                   class="w-full p-1.5 border rounded text-sm" />
          </div>
          <div class="grid grid-cols-2 gap-2">
            <div>
              <label class="block text-xs text-gray-600 mb-1">放大倍数</label>
              <select v-model.number="defocusPanel.upscale" class="w-full p-1.5 border rounded text-sm bg-white">
                <option :value="1">1×</option>
                <option :value="2">2×</option>
                <option :value="4">4×</option>
              </select>
            </div>
            <label class="flex items-center gap-2 text-xs text-gray-600 pt-5">
              <input type="checkbox" v-model="defocusPanel.faceUpsample" />
              人脸超分
            </label>
          </div>
          <button
            @click="runDefocusRestore"
            :disabled="!currentImage || isLoading"
            class="w-full px-3 py-2 bg-amber-600 hover:bg-amber-700 disabled:opacity-50 disabled:cursor-not-allowed text-white rounded-lg text-sm font-medium transition"
          >
            {{ isLoading ? '生成中...' : '生成候选' }}
          </button>
          <p v-if="defocusPanel.error" class="text-xs text-red-600 leading-relaxed">{{ defocusPanel.error }}</p>

          <div v-if="defocusPanel.results.length" class="space-y-2 pt-2 border-t border-dashed">
            <div class="text-xs text-gray-700 font-medium">候选结果(点击应用):</div>
            <div class="grid grid-cols-2 gap-2">
              <div
                v-for="r in defocusPanel.results"
                :key="r.weight"
                class="border rounded-lg p-1 cursor-pointer transition"
                :class="defocusPanel.appliedWeight === r.weight ? 'border-amber-500 ring-2 ring-amber-300' : 'border-gray-200 hover:border-amber-400'"
                @click="applyDefocusResult(r)"
              >
                <img :src="r.image" class="w-full rounded" alt="" />
                <div class="text-[10px] text-center text-gray-600 mt-1">w = {{ r.weight }}</div>
              </div>
            </div>
            <p class="text-[11px] text-gray-500">已应用 w = {{ defocusPanel.appliedWeight ?? '—' }}</p>
          </div>
        </div>
      </div>

      <div class="border rounded-xl p-4 bg-gray-50/50" :class="{ 'border-red-500 bg-red-50/10': watermarkPanel.enabled }">
        <div class="flex justify-between items-center mb-3">
          <label class="font-semibold flex items-center gap-2">
            <span class="text-sm">8.</span> 去除水印
          </label>
          <input type="checkbox" v-model="watermarkPanel.enabled" @change="onWatermarkToggle" :disabled="!currentImage" class="w-4 h-4 text-red-600" />
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

      <div class="border rounded-xl p-4 bg-gray-50/50" :class="{ 'border-orange-500 bg-orange-50/10': brushPanel.enabled }">
        <div class="flex justify-between items-center mb-3">
          <label class="font-semibold flex items-center gap-2">
            <span class="text-sm">9.</span> 涂抹打码 / 橡皮
          </label>
          <input type="checkbox" v-model="brushPanel.enabled" @change="onBrushToggle" :disabled="!currentImage" class="w-4 h-4 text-orange-600" />
        </div>
        <div v-if="brushPanel.enabled" class="pt-2 border-t border-dashed space-y-3">
          <div class="flex gap-2">
            <button
              @click="brushPanel.tool = 'mosaic'"
              :class="brushPanel.tool === 'mosaic' ? 'bg-orange-600 text-white' : 'bg-gray-200 text-gray-700'"
              class="flex-1 py-1.5 rounded text-sm font-medium transition"
            >🖌 打码</button>
            <button
              @click="brushPanel.tool = 'erase'"
              :class="brushPanel.tool === 'erase' ? 'bg-orange-600 text-white' : 'bg-gray-200 text-gray-700'"
              class="flex-1 py-1.5 rounded text-sm font-medium transition"
            >🧽 橡皮</button>
          </div>
          <div>
            <label class="flex justify-between text-xs text-gray-600 mb-1">
              <span>笔刷半径(图像像素)</span><span>{{ brushPanel.radius }}</span>
            </label>
            <input type="range" min="5" max="200" step="1" v-model.number="brushPanel.radius" class="w-full" />
          </div>
          <div v-if="brushPanel.tool === 'mosaic'">
            <label class="flex justify-between text-xs text-gray-600 mb-1">
              <span>马赛克块大小</span><span>{{ brushPanel.block }}</span>
            </label>
            <input type="range" min="2" max="60" step="1" v-model.number="brushPanel.block" class="w-full" />
          </div>
          <div class="text-xs text-gray-500 leading-relaxed">
            在左侧预览区<strong>按住鼠标拖动</strong>:打码模式刷出马赛克,橡皮模式将该圆形区域恢复为开启此模块时的底图。点「应用」后写入当前预览,可继续接其他步骤。
          </div>
          <div class="flex gap-2">
            <button @click="resetBrush"
              class="flex-1 px-3 py-2 bg-gray-200 hover:bg-gray-300 text-gray-700 rounded-lg text-sm font-medium transition">重置</button>
            <button @click="applyBrush"
              class="flex-1 px-3 py-2 bg-orange-600 hover:bg-orange-700 text-white rounded-lg text-sm font-medium transition">应用</button>
          </div>
        </div>
      </div>

    </div>
  </div>
</template>

<script setup>
import { computed, nextTick, onBeforeUnmount, onMounted, ref, reactive } from 'vue';

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
  wiener: { enabled: false, mode: 'auto', length: 15, angle: 0, noise: 0.01, autoResult: '' },
  filter: {
    enabled: false,
    type: 'none',
    params: {
      vintage:      { strength: 1.0 },
      highContrast: { alpha: 1.35, beta: 8 },
      warm:         { strength: 1.0 },
      cool:         { strength: 1.0 },
      sketch:       { blurKsize: 25, strength: 0.92 },
      emboss:       { direction: 'NW', strength: 1.0, mono: true },
      mosaic:       { block: 12 },
      vignette:     { sigmaScale: 0.5, darkness: 0.85, centerX: 0.5, centerY: 0.5 },
      motionBlur:   { ksize: 21, angle: 0 },
    },
  }
});

// 每个滤镜的默认参数(也是「恢复默认」按钮的目标值)
const FILTER_DEFAULTS = {
  vintage:      { strength: 1.0 },
  highContrast: { alpha: 1.35, beta: 8 },
  warm:         { strength: 1.0 },
  cool:         { strength: 1.0 },
  sketch:       { blurKsize: 25, strength: 0.92 },
  emboss:       { direction: 'NW', strength: 1.0, mono: true },
  mosaic:       { block: 12 },
  vignette:     { sigmaScale: 0.5, darkness: 0.85, centerX: 0.5, centerY: 0.5 },
  motionBlur:   { ksize: 21, angle: 0 },
};

const resetFilterParams = (key) => {
  const defaults = FILTER_DEFAULTS[key];
  if (!defaults) return;
  Object.assign(pipeline.filter.params[key], JSON.parse(JSON.stringify(defaults)));
  runPipeline();
};

// 把当前选中的滤镜参数(camelCase)打包成发给后端的扁平对象
const buildFilterParams = (type, params) => {
  switch (type) {
    case 'vintage':       return { strength: params.vintage.strength };
    case 'high-contrast': return { alpha: params.highContrast.alpha, beta: params.highContrast.beta };
    case 'warm':          return { warmStrength: params.warm.strength };
    case 'cool':          return { coolStrength: params.cool.strength };
    case 'sketch':        return { blurKsize: params.sketch.blurKsize, sketchStrength: params.sketch.strength };
    case 'emboss':        return { direction: params.emboss.direction, strength: params.emboss.strength, mono: params.emboss.mono };
    case 'mosaic':        return { block: params.mosaic.block };
    case 'vignette':      return { sigmaScale: params.vignette.sigmaScale, darkness: params.vignette.darkness, centerX: params.vignette.centerX, centerY: params.vignette.centerY };
    case 'motion_blur':   return { ksize: params.motionBlur.ksize, angle: params.motionBlur.angle };
    default:              return {};
  }
};

// 涂抹打码/橡皮(纯前端 Canvas,以鼠标为圆心刷区域)
const brushCanvasRef = ref(null);
let _brushOriginCanvas = null;  // 启用时刻的快照,橡皮从这里取像素
const brushPanel = reactive({
  enabled: false,
  tool: 'mosaic',  // 'mosaic' | 'erase'
  radius: 40,
  block: 12,
  drawing: false,
});

const onBrushToggle = async () => {
  if (brushPanel.enabled) {
    // 互斥:水印框选会用预览区的指针事件,冲突
    watermarkPanel.enabled = false;
    watermarkPanel.rect = null;
    watermarkPanel.selecting = false;
    await initBrushCanvas();
  } else {
    _brushOriginCanvas = null;
  }
};

const onWatermarkToggle = () => {
  if (watermarkPanel.enabled && brushPanel.enabled) {
    brushPanel.enabled = false;
    _brushOriginCanvas = null;
  }
};

const initBrushCanvas = async () => {
  if (!currentImage.value) return;
  await nextTick();
  const canvas = brushCanvasRef.value;
  if (!canvas) return;
  const img = new Image();
  img.onload = () => {
    canvas.width = img.naturalWidth;
    canvas.height = img.naturalHeight;
    canvas.getContext('2d').drawImage(img, 0, 0);
    _brushOriginCanvas = document.createElement('canvas');
    _brushOriginCanvas.width = img.naturalWidth;
    _brushOriginCanvas.height = img.naturalHeight;
    _brushOriginCanvas.getContext('2d').drawImage(img, 0, 0);
  };
  img.src = currentImage.value;
};

const brushCanvasCoords = (event) => {
  const canvas = brushCanvasRef.value;
  if (!canvas) return null;
  const rect = canvas.getBoundingClientRect();
  if (rect.width === 0 || rect.height === 0) return null;
  return {
    x: ((event.clientX - rect.left) * canvas.width) / rect.width,
    y: ((event.clientY - rect.top) * canvas.height) / rect.height,
  };
};

const applyBrushAt = (cx, cy) => {
  const canvas = brushCanvasRef.value;
  if (!canvas || !_brushOriginCanvas) return;
  const r = brushPanel.radius;
  const block = Math.max(2, brushPanel.block | 0);
  const x0 = Math.max(0, Math.floor(cx - r));
  const y0 = Math.max(0, Math.floor(cy - r));
  const x1 = Math.min(canvas.width, Math.ceil(cx + r));
  const y1 = Math.min(canvas.height, Math.ceil(cy + r));
  const w = x1 - x0;
  const h = y1 - y0;
  if (w <= 0 || h <= 0) return;

  const ctx = canvas.getContext('2d');
  const img = ctx.getImageData(x0, y0, w, h);
  const data = img.data;
  const r2 = r * r;

  if (brushPanel.tool === 'mosaic') {
    for (let by = 0; by < h; by += block) {
      for (let bx = 0; bx < w; bx += block) {
        const sx = Math.min(bx + (block >> 1), w - 1);
        const sy = Math.min(by + (block >> 1), h - 1);
        const si = (sy * w + sx) * 4;
        const R = data[si], G = data[si + 1], B = data[si + 2];
        const yEnd = Math.min(h, by + block);
        const xEnd = Math.min(w, bx + block);
        for (let dy = by; dy < yEnd; dy++) {
          const py = y0 + dy;
          const ddy = py - cy;
          const ddy2 = ddy * ddy;
          for (let dx = bx; dx < xEnd; dx++) {
            const px = x0 + dx;
            const ddx = px - cx;
            if (ddx * ddx + ddy2 <= r2) {
              const di = (dy * w + dx) * 4;
              data[di] = R; data[di + 1] = G; data[di + 2] = B;
            }
          }
        }
      }
    }
  } else {
    const origData = _brushOriginCanvas.getContext('2d').getImageData(x0, y0, w, h).data;
    for (let dy = 0; dy < h; dy++) {
      const py = y0 + dy;
      const ddy = py - cy;
      const ddy2 = ddy * ddy;
      for (let dx = 0; dx < w; dx++) {
        const px = x0 + dx;
        const ddx = px - cx;
        if (ddx * ddx + ddy2 <= r2) {
          const i = (dy * w + dx) * 4;
          data[i] = origData[i];
          data[i + 1] = origData[i + 1];
          data[i + 2] = origData[i + 2];
          data[i + 3] = origData[i + 3];
        }
      }
    }
  }
  ctx.putImageData(img, x0, y0);
};

const onBrushDown = (event) => {
  if (!brushPanel.enabled) return;
  brushPanel.drawing = true;
  const p = brushCanvasCoords(event);
  if (p) applyBrushAt(p.x, p.y);
};

const onBrushMove = (event) => {
  if (!brushPanel.drawing) return;
  const p = brushCanvasCoords(event);
  if (p) applyBrushAt(p.x, p.y);
};

const onBrushUp = () => {
  brushPanel.drawing = false;
};

const resetBrush = () => {
  if (!_brushOriginCanvas || !brushCanvasRef.value) return;
  brushCanvasRef.value.getContext('2d').drawImage(_brushOriginCanvas, 0, 0);
};

const applyBrush = () => {
  const canvas = brushCanvasRef.value;
  if (!canvas) return;
  currentImage.value = canvas.toDataURL('image/png');
  brushPanel.enabled = false;
  _brushOriginCanvas = null;
};

// 失焦恢复(CodeFormer,独立于自动流水线,手动触发,返回多个候选)
const defocusPanel = reactive({
  expanded: false,
  weightsText: '0.3, 0.4, 0.5, 0.6',
  upscale: 2,
  faceUpsample: true,
  results: [],          // [{ weight: 0.3, image: 'data:...' }, ...]
  appliedWeight: null,  // 当前选中应用的 w
  error: '',
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

    // 步骤 4: 维纳滤波去运动模糊
    if (pipeline.wiener.enabled) {
      const result = await callWienerDeblurApi(
        tempImage,
        pipeline.wiener.mode,
        pipeline.wiener.length,
        pipeline.wiener.angle,
        pipeline.wiener.noise
      );
      tempImage = result.processedImage;
      if (pipeline.wiener.mode === 'auto') {
        const params = result.params || {};
        pipeline.wiener.autoResult = params.length
          ? `自动参数：长度 ${params.length}px，角度 ${Number(params.angle || 0).toFixed(0)}°`
          : '未检测到明显运动模糊，已尽量保持原图。';
      }
    } else {
      pipeline.wiener.autoResult = '';
    }

    // 步骤 5: 滤镜
    if (pipeline.filter.enabled) {
      const fParams = buildFilterParams(pipeline.filter.type, pipeline.filter.params);
      tempImage = await callFilterApi(tempImage, pipeline.filter.type, fParams);
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

const callWienerDeblurApi = async (image, mode, motionLength, motionAngle, noisePower) => {
  const data = await postImageApi('/wiener-deblur', {
    image,
    wienerAuto: mode === 'auto',
    motionLength,
    motionAngle,
    noisePower,
  });
  return {
    processedImage: data.processedImage,
    params: data.params,
  };
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

const callFilterApi = async (image, filterType, filterParams = {}) => {
  const data = await postImageApi('/filter', { image, filterType, filterParams });
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

const parseDefocusWeights = (text) => {
  const arr = (text || '')
    .split(/[,，\s]+/)
    .map((s) => parseFloat(s))
    .filter((n) => Number.isFinite(n) && n >= 0 && n <= 1);
  return Array.from(new Set(arr.map((n) => Math.round(n * 100) / 100))).sort((a, b) => a - b);
};

const runDefocusRestore = async () => {
  if (!currentImage.value) return;
  defocusPanel.error = '';
  const weights = parseDefocusWeights(defocusPanel.weightsText);
  if (!weights.length) {
    defocusPanel.error = '请填入至少一个 0~1 的 w 值,例如:0.3, 0.4, 0.5, 0.6';
    return;
  }
  isLoading.value = true;
  try {
    const data = await postImageApi('/defocus-restore', {
      image: currentImage.value,
      defocusWeights: weights,
      defocusUpscale: defocusPanel.upscale,
      defocusFaceUpsample: defocusPanel.faceUpsample,
    });
    defocusPanel.results = (data.results || []).map((r) => ({
      weight: r.weight,
      image: r.image,
    }));
    defocusPanel.appliedWeight = null;
  } catch (error) {
    console.error('失焦恢复失败:', error);
    const msg = error?.response?.data?.detail || error?.message || String(error);
    defocusPanel.error = `失焦恢复失败:${msg}`;
  } finally {
    isLoading.value = false;
  }
};

const applyDefocusResult = (item) => {
  if (!item) return;
  currentImage.value = item.image;
  defocusPanel.appliedWeight = item.weight;
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
  pipeline.wiener = { enabled: false, mode: 'auto', length: 15, angle: 0, noise: 0.01, autoResult: '' };
  pipeline.filter = {
    enabled: false,
    type: 'none',
    params: {
      vintage:      { strength: 1.0 },
      highContrast: { alpha: 1.35, beta: 8 },
      warm:         { strength: 1.0 },
      cool:         { strength: 1.0 },
      sketch:       { blurKsize: 25, strength: 0.92 },
      emboss:       { direction: 'NW', strength: 1.0, mono: true },
      mosaic:       { block: 12 },
      vignette:     { sigmaScale: 0.5, darkness: 0.85, centerX: 0.5, centerY: 0.5 },
      motionBlur:   { ksize: 21, angle: 0 },
    },
  };
  aiPanel.expanded = false;
  aiPanel.style = 'webtoon';
  aiPanel.strength = 0.6;
  aiPanel.seed = 42;
  aiPanel.applied = false;
  defocusPanel.expanded = false;
  defocusPanel.weightsText = '0.3, 0.4, 0.5, 0.6';
  defocusPanel.upscale = 2;
  defocusPanel.faceUpsample = true;
  defocusPanel.results = [];
  defocusPanel.appliedWeight = null;
  defocusPanel.error = '';
  watermarkPanel.enabled = false;
  watermarkPanel.type = 'white';
  watermarkPanel.radius = 3;
  watermarkPanel.rect = null;
  watermarkPanel.selecting = false;
  brushPanel.enabled = false;
  brushPanel.tool = 'mosaic';
  brushPanel.radius = 40;
  brushPanel.block = 12;
  brushPanel.drawing = false;
  _brushOriginCanvas = null;
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
