"use strict";
(() => {
  const hero = document.querySelector(".hero");
  const experience = document.getElementById("touch-experience");
  const surface = document.getElementById("touch-surface");
  const output = document.getElementById("touch-event");
  const announcer = document.getElementById("touch-status");
  const fill = document.getElementById("signal-fill");
  const cells = [...document.querySelectorAll("#taxel-map span")];
  const intensity = document.getElementById("touch-pressure");
  const amount = document.getElementById("pressure-value");
  const toggle = document.getElementById("motion-toggle");
  const canvas = document.getElementById("field-canvas");
  const ctx = canvas.getContext("2d");
  const art = document.querySelector(".hero-art");
  const marker = document.querySelector(".touch-target");
  const prompt = document.querySelector(".touch-prompt");
  const reduced = window.matchMedia("(prefers-reduced-motion: reduce)");
  let paused = reduced.matches;
  let active = false;
  let pointer = null;
  let origin = {x: 0, y: 0};
  let target = {x: .7, y: .5};
  let state = "standby";
  let width = 1, height = 1;
  let frame = null, previous = 0;
  let insideViewport = true;
  let sequence = 0, resetTimer = null;
  let waves = [];
  const particles = Array.from({length: 38}, (_, i) => ({
    x: ((i * 73 + 19) % 997) / 997,
    y: ((i * 131 + 11) % 991) / 991,
    speed: .000008 + (i % 4) * .000004,
    radius: i % 3 === 0 ? 2 : 1,
  }));
  const translate = key => typeof t === "function" ? t(key) : key;
  function updateMotionLabel() {
    toggle.textContent = translate(paused ? "touch.resume" : "touch.pause");
    toggle.setAttribute("aria-pressed", String(paused));
    hero.classList.toggle("effects-paused", paused);
  }
  function paintSignal(level, x = .5, y = .5) {
    cells.forEach((cell, i) => {
      const distance = Math.hypot((i % 4) / 3 - x, Math.floor(i / 4) / 3 - y);
      cell.style.setProperty("--level", String(.08 + Math.max(0, 1 - distance) * level * .9));
    });
    fill.style.width = `${level * 100}%`;
  }
  function setState(next) {
    if (state === next) return;
    state = next;
    output.textContent = next;
    announcer.textContent = translate("touch.announcement") + next;
  }
  function position(x, y) {
    const rect = hero.getBoundingClientRect();
    target = {x: Math.max(0,Math.min(1,(x-rect.left)/rect.width)),y:Math.max(0,Math.min(1,(y-rect.top)/rect.height))};
  }
  function burst() {
    if (paused) return;
    waves.push({x:target.x,y:target.y,birth:performance.now()});
    if (waves.length > 8) waves.shift();
    startAnimation();
  }
  function begin(x, y) {
    clearTimeout(resetTimer);
    sequence++;
    active = true;
    origin = {x,y};
    position(x,y);
    experience.classList.add("is-touching");
    setState("contact_begin");
    paintSignal(Number(intensity.value)/100);
    burst();
  }
  function end() {
    if (!active) return;
    active = false;
    pointer = null;
    experience.classList.remove("is-touching");
    setState("contact_end");
    paintSignal(0);
    burst();
    const current = sequence;
    resetTimer = setTimeout(() => {if (!active && sequence === current) setState("standby");},1600);
  }
  surface.addEventListener("pointerdown", event => {
    if (!event.isPrimary || event.button !== 0) return;
    pointer = event.pointerId;
    surface.setPointerCapture(event.pointerId);
    begin(event.clientX,event.clientY);
  });
  surface.addEventListener("pointermove", event => {
    if (pointer !== null && pointer !== event.pointerId) return;
    position(event.clientX,event.clientY);
    if (!active) return;
    const rect = surface.getBoundingClientRect();
    const x = Math.max(0,Math.min(1,(event.clientX-rect.left)/rect.width));
    const y = Math.max(0,Math.min(1,(event.clientY-rect.top)/rect.height));
    paintSignal(Number(intensity.value)/100,x,y);
    if (Math.hypot(event.clientX-origin.x,event.clientY-origin.y)>14) {
      if(state !== "slip") burst();
      setState("slip");
    }
  });
  ["pointerup","pointercancel","lostpointercapture"].forEach(type => surface.addEventListener(type, event => {
    if (event.pointerId === pointer) end();
  }));
  surface.addEventListener("click",event => {
    if (event.detail !== 0 || active) return;
    const rect = marker.getBoundingClientRect();
    begin(rect.left+rect.width*.5,rect.top+rect.height*.5);
    resetTimer = setTimeout(end,650);
  });
  intensity.addEventListener("input", () => {
    amount.value = `${intensity.value}%`;
    amount.textContent = amount.value;
    if(active)paintSignal(Number(intensity.value)/100);
  });
  // Project the fingertip in the artwork into the interaction surface, including
  // cover cropping at narrow widths. Keep the visual target on the fingertip.
  function alignTarget() {
    if (!art.naturalWidth) return;
    const box = art.getBoundingClientRect();
    const surfaceBox = surface.getBoundingClientRect();
    const fit = Math.max(box.width / art.naturalWidth, box.height / art.naturalHeight);
    const renderedWidth = art.naturalWidth * fit;
    const renderedHeight = art.naturalHeight * fit;
    const parts = getComputedStyle(art).objectPosition.split(" ");
    const fraction = value => value === "center" ? .5 : parseFloat(value) / 100;
    const x = box.left + (box.width-renderedWidth)*fraction(parts[0]) + renderedWidth*.665 - surfaceBox.left;
    const y = box.top + (box.height-renderedHeight)*fraction(parts[1] || "50%") + renderedHeight*.695 - surfaceBox.top;
    marker.style.left = prompt.style.left = `${x}px`;
    marker.style.top = `${y}px`;
    prompt.style.top = `${y+65}px`;
  }
  function resize() {
    alignTarget();
    const rect = hero.getBoundingClientRect();
    width = rect.width; height = rect.height;
    const scale = Math.min(window.devicePixelRatio || 1,2);
    canvas.width = Math.round(width*scale);canvas.height = Math.round(height*scale);
    if(ctx)ctx.setTransform(scale,0,0,scale,0,0);
    if(paused && ctx)draw(performance.now(),0);
    startAnimation();
  }
  function draw(now,delta) {
    if(!ctx)return;
    ctx.clearRect(0,0,width,height);
    // Quiet field lines and drifting signal points; no external render dependency.
    ctx.lineWidth=.6;
    for(let row=0;row<8;row++){
      ctx.beginPath();
      for(let x=0;x<=width;x+=22){
        const wave=paused?0:Math.sin(x*.006+now*.0003+row*.4)*9;
        const y=height*.72+row*22+wave;
        if(x===0)ctx.moveTo(x,y);else ctx.lineTo(x,y);
      }
      ctx.strokeStyle=`rgba(10,136,170,${.025+row*.004})`;ctx.stroke();
    }
    particles.forEach(p => {
      if(!paused)p.y=(p.y-delta*p.speed+1)%1;
      const x=p.x*width,y=p.y*height;
      ctx.beginPath();ctx.arc(x,y,p.radius,0,Math.PI*2);
      ctx.fillStyle="rgba(1,151,186,.28)";ctx.fill();
      if(active && Math.hypot(x-target.x*width,y-target.y*height)<160){
        ctx.beginPath();ctx.moveTo(x,y);ctx.lineTo(target.x*width,target.y*height);
        ctx.strokeStyle="rgba(0,151,191,.16)";ctx.stroke();
      }
    });
    waves=waves.filter(w=>now-w.birth<1300);
    waves.forEach(w=>{
      const progress=(now-w.birth)/1300;
      ctx.beginPath();ctx.ellipse(w.x*width,w.y*height,16+progress*155,8+progress*65,-.25,0,Math.PI*2);
      ctx.strokeStyle=`rgba(0,167,205,${(1-progress)*.65})`;ctx.lineWidth=1.5;ctx.stroke();
    });
  }
  function tick(now) {
    frame=null;
    if(paused || document.hidden || !insideViewport || !ctx)return;
    if(now-previous>=32){draw(now,Math.min(now-previous,40));previous=now;}
    frame=requestAnimationFrame(tick);
  }
  function startAnimation() {
    if(frame===null && !paused && !document.hidden && insideViewport && ctx){previous=performance.now();frame=requestAnimationFrame(tick);}
  }
  function stopAnimation() {if(frame!==null)cancelAnimationFrame(frame);frame=null;}
  toggle.addEventListener("click",()=>{
    paused=!paused;waves=[];updateMotionLabel();
    if(paused){stopAnimation();draw(performance.now(),0);}else startAnimation();
  });
  reduced.addEventListener("change",event=>{
    paused=event.matches;updateMotionLabel();
    if(paused){stopAnimation();waves=[];draw(performance.now(),0);}else startAnimation();
  });
  document.addEventListener("tacstack:language",()=>{updateMotionLabel();resize();});
  art.addEventListener("load",resize);
  document.addEventListener("visibilitychange",()=>{if(document.hidden){end();stopAnimation();}else startAnimation();});
  window.addEventListener("blur",end);
  window.addEventListener("resize",resize,{passive:true});
  if("IntersectionObserver" in window){
    new IntersectionObserver(entries=>{insideViewport=entries[0].isIntersecting;if(insideViewport)startAnimation();else{end();stopAnimation();}},{threshold:0}).observe(hero);
  }
  updateMotionLabel();resize();paintSignal(0);
})();
