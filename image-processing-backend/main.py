from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from api.image_routes import router as image_router

app = FastAPI(title="图像智能校正系统后端")

# 必须配置跨域，否则前端 Vue/React 无法访问
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"], # 允许所有前端源，本地开发用
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# 注册我们刚才写的路由
app.include_router(image_router)

if __name__ == "__main__":
    import uvicorn
    # 启动服务，运行在本地 8000 端口
    uvicorn.run("main:app", host="127.0.0.1", port=8000, reload=True)