const starsEl = document.getElementById("stars");
for(let i=0;i<100;i++){
  const d=document.createElement("div");
  d.className="star-dot";
  const s=Math.random()*2.5+0.5;
  d.style.cssText=`width:${s}px;height:${s}px;left:${Math.random()*100}%;top:${Math.random()*100}%;--d:${(Math.random()*4+2).toFixed(1)}s;--delay:${(Math.random()*4).toFixed(1)}s;--min:${(Math.random()*0.12).toFixed(2)};--max:${(Math.random()*0.6+0.15).toFixed(2)};`;
  starsEl.appendChild(d);
}
for(let i=0;i<15;i++){
  const d=document.createElement("div");
  d.className="star-dot";
  const s=Math.random()*2+1;
  d.style.cssText=`width:${s}px;height:${s}px;left:${Math.random()*100}%;top:${Math.random()*100}%;background:#c084fc;--d:${(Math.random()*5+3).toFixed(1)}s;--delay:${(Math.random()*5).toFixed(1)}s;--min:0.05;--max:0.45;`;
  starsEl.appendChild(d);
}

const obs=new IntersectionObserver(entries=>{
  entries.forEach(e=>{
    if(e.isIntersecting){e.target.classList.add("visible");}
  });
},{threshold:0.12,rootMargin:"0px 0px -30px 0px"});
document.querySelectorAll(".reveal,.tl-item").forEach((el,i)=>{
  if(el.classList.contains("tl-item")) el.style.transitionDelay=`${i*0.1}s`;
  obs.observe(el);
});

// Character Sheet Tab Switch
function switchCS(v) {
  document.getElementById('cs-panel-1').classList.toggle('active', v === 1);
  document.getElementById('cs-panel-2').classList.toggle('active', v === 2);
  document.getElementById('tab-v1').classList.toggle('active', v === 1);
  document.getElementById('tab-v2').classList.toggle('active', v === 2);
  document.getElementById('cs-caption').textContent = v === 1
    ? 'ชุด PRIVATE GOD\'S TOY · Punk Rock Street Fashion — 2025'
    : 'ชุดเดบิวต์ · ชุดเทวดา/มังกร · และดีเทลต่างๆ ของนานะ — 2026';
}

// Smooth scroll โดยไม่เปลี่ยน URL
  document.querySelectorAll('a[href^="#"]').forEach(link => {
      link.addEventListener('click', (e) => {
          e.preventDefault();
          const target = document.querySelector(link.getAttribute('href'));
          if (target) {
              target.scrollIntoView({ behavior: 'smooth' });
          }
      });
  });
