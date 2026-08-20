from __future__ import annotations

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import HTMLResponse

from medical_rag.api.routes.auth import router as auth_router
from medical_rag.api.routes.knowledge import router as knowledge_router
from medical_rag.api.routes.patients import router as patients_router
from medical_rag.api.routes.rag import assistant_router, router as rag_router
from medical_rag.core.config import get_settings
from medical_rag.rag.pipeline import verify_runtime_paths
from medical_rag.rag.runtime import get_runtime_status

settings = get_settings()
app = FastAPI(
    title="medical-rag",
    version="1.0.0",
    description="Medical knowledge retrieval augmented generation service",
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://127.0.0.1:5173", "http://localhost:5173"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(auth_router)
app.include_router(patients_router)
app.include_router(knowledge_router)
app.include_router(rag_router)
app.include_router(assistant_router)


@app.get("/health", tags=["system"])
async def health() -> dict:
    runtime = get_runtime_status()
    readiness_errors = settings.rag_readiness_errors()
    return {
        "status": "ok",
        "service": settings.app_name,
        "environment": settings.app_env,
        "version": "1.0.0",
        "rag": {
            "configured": not readiness_errors,
            "loaded": runtime.loaded,
            "loading": runtime.loading,
            "error": runtime.error,
            "dense_backend": settings.rag_dense_backend,
            "paths": verify_runtime_paths(settings),
            "configuration_errors": readiness_errors,
        },
    }


@app.get("/api/v1/system/info", tags=["system"])
async def system_info() -> dict:
    return {
        "project": "JD 特定人群生理孪生与医疗保障大模型平台",
        "module": "多源图文医疗知识增强检索子系统",
        "version": "1.0.0",
        "current_scope": "医疗指南单知识库问答 V1.0",
        "capabilities": [
            "混合检索",
            "神经重排序",
            "Milvus向量检索",
            "证据上下文构建",
            "大模型生成",
            "引用追踪",
            "证据不足拒答",
            "个体化医疗安全边界",
        ],
    }


@app.get("/rag-demo", response_class=HTMLResponse, include_in_schema=False)
async def rag_demo() -> str:
    """Small zero-build demo page.

    The repository's Vue front end is preserved separately. This page exists so
    the backend package alone can already be demonstrated without rebuilding the
    front-end project.
    """

    return _DEMO_HTML


_DEMO_HTML = r'''<!doctype html>
<html lang="zh-CN">
<head>
<meta charset="utf-8" />
<meta name="viewport" content="width=device-width,initial-scale=1" />
<title>Medical RAG V1.0</title>
<style>
body{margin:0;background:#f5f7fb;color:#1f2937;font-family:-apple-system,BlinkMacSystemFont,"Segoe UI",sans-serif}
.wrap{max-width:1050px;margin:36px auto;padding:0 20px}.card{background:#fff;border:1px solid #e5e7eb;border-radius:16px;padding:22px;margin-bottom:18px;box-shadow:0 8px 28px rgba(15,23,42,.05)}
h1{margin:0 0 8px;font-size:26px}.muted{color:#6b7280;font-size:14px}.row{display:flex;gap:10px;flex-wrap:wrap}.row input{flex:1;min-width:180px}
input,textarea{box-sizing:border-box;width:100%;border:1px solid #d1d5db;border-radius:10px;padding:11px 12px;font-size:15px;background:#fff}textarea{min-height:92px;resize:vertical}
button{border:0;border-radius:10px;padding:11px 18px;font-size:15px;cursor:pointer;background:#2563eb;color:#fff}button:disabled{opacity:.55;cursor:not-allowed}.secondary{background:#475569}
.answer{white-space:pre-wrap;line-height:1.75;font-size:16px}.source{border-top:1px solid #eef2f7;padding:14px 0}.badge{display:inline-block;background:#eff6ff;color:#1d4ed8;border-radius:999px;padding:3px 9px;font-size:12px;margin-right:6px}.used{background:#ecfdf5;color:#047857}
pre{white-space:pre-wrap;word-break:break-word;background:#f8fafc;padding:12px;border-radius:10px;font-size:12px;max-height:260px;overflow:auto}.status{font-size:13px;margin-top:8px;color:#64748b}.error{color:#b91c1c}
</style>
</head>
<body><div class="wrap">
<div class="card"><h1>医疗知识库问答 V1.0</h1><div class="muted">真实链路：混合检索 → 重排序 → 证据上下文 → 大模型回答 → 引用追踪</div></div>
<div class="card"><h3>1. 本地演示登录</h3><div class="row"><input id="user" value="doctor" placeholder="账号"><input id="pass" value="123456" type="password" placeholder="密码"><button onclick="login()">登录</button></div><div id="loginStatus" class="status">尚未登录</div></div>
<div class="card"><h3>2. 提问</h3><textarea id="question">2级高血压的收缩压和舒张压范围是多少？</textarea><div style="margin-top:10px"><button id="askBtn" onclick="ask()">发送问题</button></div><div id="askStatus" class="status"></div></div>
<div class="card"><h3>回答</h3><div id="answer" class="answer muted">等待提问……</div></div>
<div class="card"><h3>证据来源</h3><div id="sources" class="muted">暂无</div></div>
<div class="card"><h3>运行诊断</h3><pre id="diag">暂无</pre></div>
</div>
<script>
let token='';
async function login(){
 const r=await fetch('/api/v1/auth/login',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({username:document.getElementById('user').value,password:document.getElementById('pass').value})});
 const el=document.getElementById('loginStatus'); if(!r.ok){el.textContent='登录失败';el.className='status error';return;} const d=await r.json();token=d.accessToken;el.textContent='登录成功';el.className='status';
}
async function ask(){
 const btn=document.getElementById('askBtn'); btn.disabled=true; document.getElementById('askStatus').textContent='正在检索和生成，请稍候……';
 try{const r=await fetch('/api/v1/rag/ask',{method:'POST',headers:{'Content-Type':'application/json','Authorization':'Bearer '+token},body:JSON.stringify({question:document.getElementById('question').value})});const d=await r.json();if(!r.ok) throw new Error(d.detail||'请求失败');document.getElementById('answer').textContent=d.answer;document.getElementById('answer').className='answer';document.getElementById('diag').textContent=JSON.stringify(d.diagnostics,null,2);const box=document.getElementById('sources');box.innerHTML='';d.sources.forEach(s=>{const div=document.createElement('div');div.className='source';div.innerHTML=`<span class="badge">${s.citation_id}</span>${s.used_in_answer?'<span class="badge used">答案已引用</span>':''}<b>${s.source_file}</b> · 第${s.page_start===s.page_end?s.page_start:s.page_start+'-'+s.page_end}页${s.section?' · '+s.section:''}<pre>${s.text}</pre>`;box.appendChild(div)});document.getElementById('askStatus').textContent=d.abstained?'系统因证据不足进行了拒答':'完成';}
 catch(e){document.getElementById('askStatus').textContent=e.message;document.getElementById('askStatus').className='status error';}
 finally{btn.disabled=false;}
}
</script></body></html>'''
