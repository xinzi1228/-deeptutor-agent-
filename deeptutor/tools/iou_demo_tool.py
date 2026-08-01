"""IOU interactive demo tool — feynman-style visual handoff.

When the coach explains IOU (交并比), instead of making the learner reason
through the formula abstractly, this tool produces a single-file interactive
HTML demo: two draggable/resizable boxes on a canvas with a live IOU readout.
The visualization is delivered as a file path/URL and does not take over the
conversation rhythm (feynman grimoire pattern) — the coach keeps teaching in
text around it.
"""

from __future__ import annotations

from typing import Any

from deeptutor.core.tool_protocol import BaseTool, ToolDefinition, ToolParameter, ToolResult

_DEMO_HTML = """<!DOCTYPE html>
<html lang="zh">
<head>
<meta charset="utf-8">
<title>IOU 交并比交互演示</title>
<style>
  body { font-family: -apple-system, "Microsoft YaHei", sans-serif; background:#f8fafc;
         margin:0; padding:20px; color:#1e293b; }
  .wrap { max-width: 860px; margin: 0 auto; }
  h1 { font-size: 18px; }
  canvas { background:#fff; border:1px solid #cbd5e1; border-radius:8px; cursor:crosshair;
           display:block; margin:12px 0; }
  .bar { display:flex; gap:16px; flex-wrap:wrap; align-items:center; }
  .score { font-size:20px; font-weight:700; padding:6px 14px; border-radius:8px; }
  .good { background:#dcfce7; color:#15803d; }
  .mid { background:#fef9c3; color:#a16207; }
  .bad { background:#fee2e2; color:#b91c1c; }
  .legend { font-size:13px; color:#475569; }
  .btn { padding:6px 12px; border-radius:6px; border:1px solid #cbd5e1; background:#fff;
         cursor:pointer; font-size:13px; }
  .btn:hover { background:#f1f5f9; }
  .hint { font-size:13px; color:#64748b; margin-top:8px; }
</style>
</head>
<body>
<div class="wrap">
  <h1>IOU 交并比 — 拖动两个框实时看变化</h1>
  <div class="legend">蓝色 = 预测框 (A)，绿色 = 真值框 (B)。拖方块角缩放，拖内部移动。完全重叠 = 1.0，不相交 = 0.0。</div>
  <canvas id="c" width="780" height="440"></canvas>
  <div class="bar">
    <span class="score" id="iou">IOU: 0.00</span>
    <span class="score mid" id="intersect">交集: 0</span>
    <span class="score mid" id="union">并集: 0</span>
    <button class="btn" id="reset">重置</button>
  </div>
  <div class="hint">思考：<br>1. 两个框完全重合时 IOU 是多少？<br>2. 框 A 很大但框 B 很小且都在 B 内时，IOU 高还是低？为什么？<br>3. 为什么要用「交集/并集」而不是「交集/A」来衡量？</div>
</div>
<script>
const c = document.getElementById('c'), ctx = c.getContext('2d');
const A = {x:180, y:140, w:180, h:140};
const B = {x:330, y:220, w:180, h:140};
let drag = null;
function iou(a,b){
  const ix = Math.max(0, Math.min(a.x+a.w,b.x+b.w) - Math.max(a.x,b.x));
  const iy = Math.max(0, Math.min(a.y+a.h,b.y+b.h) - Math.max(a.y,b.y));
  const inter = ix*iy, uni = a.w*a.h + b.w*b.h - inter;
  return [inter, uni, uni>0? inter/uni : 0];
}
function inside(p, r, tol=6){
  return p.x>=r.x-tol && p.x<=r.x+r.w+tol && p.y>=r.y-tol && p.y<=r.y+r.h+tol;
}
function corner(p, r){
  const pts = [[r.x,r.y],[r.x+r.w,r.y],[r.x+r.w,r.y+r.h],[r.x,r.y+r.h]];
  for(let i=0;i<4;i++) if(Math.hypot(p.x-pts[i][0],p.y-pts[i][1])<10) return i;
  return -1;
}
function hit(p){
  if(inside(p,A)) return {box:'A', part:'move'};
  if(inside(p,B)) return {box:'B', part:'move'};
  const a=corner(p,A), b=corner(p,B);
  if(a>=0) return {box:'A', part:'corner', i:a};
  if(b>=0) return {box:'B', part:'corner', i:b};
  return null;
}
function draw(){
  ctx.clearRect(0,0,c.width,c.height);
  const [inter, uni, score] = iou(A,B);
  // union shading
  ctx.fillStyle = 'rgba(59,130,246,0.08)';
  ctx.fillRect(Math.min(A.x,B.x), Math.min(A.y,B.y),
     Math.max(A.x+A.w,B.x+B.w)-Math.min(A.x,B.x), Math.max(A.y+A.h,B.y+B.h)-Math.min(A.y,B.y));
  // intersection
  const ix = Math.max(A.x,B.x), iy=Math.max(A.y,B.y);
  const iw = Math.max(0,Math.min(A.x+A.w,B.x+B.w)-ix), ih=Math.max(0,Math.min(A.y+A.h,B.y+B.h)-iy);
  if(iw>0&&ih>0){ ctx.fillStyle='rgba(168,85,247,0.5)'; ctx.fillRect(ix,iy,iw,ih); }
  // A
  ctx.strokeStyle='#3b82f6'; ctx.lineWidth=2; ctx.strokeRect(A.x,A.y,A.w,A.h);
  ctx.fillStyle='rgba(59,130,246,0.15)'; ctx.fillRect(A.x,A.y,A.w,A.h);
  // B
  ctx.strokeStyle='#22c55e'; ctx.lineWidth=2; ctx.setLineDash([5,4]); ctx.strokeRect(B.x,B.y,B.w,B.h);
  ctx.setLineDash([]); ctx.fillStyle='rgba(34,197,94,0.12)'; ctx.fillRect(B.x,B.y,B.w,B.h);
  const scoreEl=document.getElementById('iou'), ie=document.getElementById('intersect'), ue=document.getElementById('union');
  scoreEl.textContent='IOU: '+score.toFixed(2);
  ie.textContent='交集: '+inter+'px²';
  ue.textContent='并集: '+uni+'px²';
  scoreEl.className='score '+(score>=0.5?'good':(score>0.2?'mid':'bad'));
}
c.addEventListener('mousedown', e=>{
  const r=c.getBoundingClientRect();
  drag=hit({x:e.clientX-r.left, y:e.clientY-r.top});
});
c.addEventListener('mousemove', e=>{
  const r=c.getBoundingClientRect(), p={x:e.clientX-r.left, y:e.clientY-r.top};
  if(!drag){ c.style.cursor=hit(p)?'pointer':'crosshair'; return; }
  const box = drag.box==='A'?A:B;
  if(drag.part==='move'){ box.x=p.x-box.w/2; box.y=p.y-box.h/2; }
  else {
    const corners=[[box.x,box.y],[box.x+box.w,box.y],[box.x+box.w,box.y+box.h],[box.x,box.y+box.h]];
    const [ox,oy]=corners[drag.i];
    const dw=p.x-ox, dh=p.y-oy;
    if(drag.i===0){ box.x=Math.min(p.x,ox); box.y=Math.min(p.y,oy); box.w=Math.abs(p.x-ox); box.h=Math.abs(p.y-oy); }
    if(drag.i===1){ box.y=Math.min(p.y,oy); box.w=p.x-box.x; box.h=Math.abs(p.y-oy); }
    if(drag.i===2){ box.w=p.x-box.x; box.h=p.y-box.y; }
    if(drag.i===3){ box.x=p.x; box.h=p.y-box.y; box.w=Math.abs(p.x-ox); }
    box.w=Math.max(20,box.w); box.h=Math.max(20,box.h);
  }
  draw();
});
window.addEventListener('mouseup', ()=>{ drag=null; });
document.getElementById('reset').addEventListener('click', ()=>{
  Object.assign(A,{x:180,y:140,w:180,h:140}); Object.assign(B,{x:330,y:220,w:180,h:140}); draw();
});
draw();
</script>
</body>
</html>
"""


class GenerateIouDemoTool(BaseTool):
    """Generate an interactive IOU demonstration HTML file."""

    def get_definition(self) -> ToolDefinition:
        return ToolDefinition(
            name="generate_iou_demo",
            description=(
                "Generate an interactive IOU (交并比) demonstration: two draggable boxes "
                "with a live IOU/intersection/union readout, delivered as an HTML file "
                "the student opens in the browser. Call this when teaching IOU — the "
                "demo complements (never replaces) the text explanation. The visualization "
                "is handed off as a file URL; keep teaching around it."
            ),
            parameters=[],
        )

    async def execute(self, **kwargs: Any) -> ToolResult:
        from deeptutor.services.path_service import get_path_service

        try:
            task_dir = get_path_service().get_task_workspace("chat", "iou_demo")
            demo_dir = task_dir / "demos"
            demo_dir.mkdir(parents=True, exist_ok=True)
            demo_file = demo_dir / "iou_demo.html"
            demo_file.write_text(_DEMO_HTML, encoding="utf-8")

            from deeptutor.services.sandbox.artifacts import collect_public_artifacts

            artifacts = collect_public_artifacts(str(demo_dir))
            if not artifacts:
                return ToolResult(
                    content="IOU demo generated but not exposed publicly.",
                    success=False,
                )
            artifact = artifacts[0]
            return ToolResult(
                content=(
                    "已生成 IOU 交并比交互演示！\n\n"
                    f"**打开演示**: {artifact.url}\n\n"
                    "两个框可以拖动/缩放，IOU 实时更新。引导学生思考：\n"
                    "1. 完全重合时 IOU=1.0\n"
                    "2. 大框套小框时 IOU 高还是低？\n"
                    "3. 为什么要交集/并集而不是交集/单框？"
                ),
                sources=[
                    {
                        "type": "artifact",
                        "filename": artifact.filename,
                        "url": artifact.url,
                        "path": artifact.path,
                        "mime_type": artifact.mime_type,
                        "size_bytes": artifact.size_bytes,
                    }
                ],
                metadata={
                    "artifact": artifact.to_dict(),
                    "task_id": "iou_demo",
                },
            )
        except Exception as exc:
            return ToolResult(
                content=f"Failed to generate IOU demo: {exc}",
                success=False,
            )


__all__ = ["GenerateIouDemoTool"]
