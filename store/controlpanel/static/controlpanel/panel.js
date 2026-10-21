(() => {
  const toggle = document.querySelector('.cp-menu-toggle');
  toggle?.addEventListener('click', () => {
    const open = document.querySelector('.cp-sidebar').classList.toggle('is-open');
    toggle.setAttribute('aria-expanded', String(open));
  });
})();

(() => {
  const digits=new Intl.NumberFormat('fa-IR');
  const dialog=document.querySelector('[data-sync-dialog]');
  const stage=document.querySelector('[data-sync-stage]'),progress=document.querySelector('[data-sync-progress]'),message=document.querySelector('[data-sync-message]');
  document.querySelector('[data-sync-close]')?.addEventListener('click',()=>dialog.close());
  let polling=false;
  async function poll(url){
    polling=true;
    while(polling){
      try{
        const response=await fetch(url,{cache:'no-store'});if(!response.ok)throw new Error();const data=await response.json();
        stage.textContent=data.stage||'در حال همگام‌سازی';progress.value=data.progress;document.querySelector('[data-sync-percent]').textContent=digits.format(data.progress)+'٪';
        message.textContent=data.message||'این کار در پس‌زمینه ادامه دارد.';
        if(data.status!=='running'){polling=false;stage.textContent=data.status==='failed'?'همگام‌سازی انجام نشد':'همگام‌سازی تکمیل شد';document.querySelectorAll('[data-sync-form] button').forEach(b=>b.disabled=false);break;}
      }catch{message.textContent='دریافت وضعیت فعلاً ممکن نیست؛ گزارش همگام‌سازی را بررسی کنید.';}
      await new Promise(resolve=>setTimeout(resolve,1800));
    }
  }
  document.querySelectorAll('[data-sync-form]').forEach(form=>form.addEventListener('submit',async event=>{
    event.preventDefault();if(polling){if(!dialog.open)dialog.showModal();return;}
    dialog.showModal();progress.value=0;stage.textContent='در حال شروع…';message.textContent='';form.querySelector('button').disabled=true;
    try{const response=await fetch(form.action,{method:'POST',body:new FormData(form),headers:{Accept:'application/json'}});const data=await response.json();if(!response.ok)throw new Error(data.error);poll(data.status_url);}catch(error){message.textContent=error.message||'شروع همگام‌سازی انجام نشد.';form.querySelector('button').disabled=false;}
  }));
  const running=document.querySelector('[data-running-sync]');if(running){dialog.showModal();poll(running.dataset.runningSync);}
  const form=document.querySelector('[data-description-form]');
  form?.querySelector('[data-description-generate]').addEventListener('click',async event=>{
    const button=event.currentTarget,status=form.querySelector('[data-description-status]');button.disabled=true;status.textContent='در حال جستجو در اینترنت و ساخت پیش‌نویس توضیحات…';
    try{const body=new FormData(form);body.set('action','generate');const response=await fetch(location.href,{method:'POST',body});const data=await response.json();if(!response.ok)throw new Error(data.error);form.querySelector('textarea').value=data.description;const sources=form.querySelector('[data-description-sources]');sources.replaceChildren();for(const source of data.sources||[]){const a=document.createElement('a');a.href=source.url;a.target='_blank';a.rel='noopener noreferrer';a.textContent=source.title;sources.append(a);}status.textContent='پیش‌نویس آماده شد؛ بررسی کنید و سپس ذخیره کنید.';}catch(error){status.textContent=error.message;}finally{button.disabled=false;}
  });
  document.querySelector('[data-story-show-price]')?.addEventListener('change',event=>{document.querySelectorAll('[data-story]').forEach(card=>{card.querySelector('[data-story-price]').textContent=event.target.checked?digits.format(Number(card.dataset.price))+' ریال':'برای سفارش با ما تماس بگیرید';});});
  document.querySelectorAll('[data-story-download]').forEach(button=>button.addEventListener('click',async()=>{
    const card=button.closest('[data-story]'),d=card.dataset,status=card.querySelector('[data-story-status]');button.disabled=true;status.textContent='در حال آماده‌سازی استوری…';
    try{
      await document.fonts.ready;const img=new Image();img.src=d.image;await img.decode();
      const canvas=document.createElement('canvas');canvas.width=1080;canvas.height=1920;const ctx=canvas.getContext('2d');
      const bg=ctx.createLinearGradient(0,0,1080,1920);bg.addColorStop(0,'#022e21');bg.addColorStop(1,'#102c45');ctx.fillStyle=bg;ctx.fillRect(0,0,1080,1920);
      try{const logo=new Image();logo.src=d.logo;await logo.decode();ctx.drawImage(logo,75,35,140,140);}catch{}ctx.fillStyle='#a0bddb';ctx.beginPath();ctx.arc(1050,350,390,0,Math.PI*2);ctx.fill();ctx.fillStyle='#e4fd97';ctx.fillRect(80,180,100,9);
      ctx.direction='rtl';ctx.textAlign='right';ctx.fillStyle='#eff7ff';ctx.font='bold 52px Vazirmatn';ctx.fillText(d.shop,1000,130,920);ctx.font='30px Vazirmatn';ctx.fillStyle='#bcd7e8';ctx.fillText('پخش عمده لوازم یدکی · انتخاب امروز',1000,230,900);
      ctx.fillStyle='#f0f6fa';ctx.beginPath();ctx.roundRect(80,330,920,790,48);ctx.fill();const scale=Math.min(790/img.width,650/img.height);ctx.drawImage(img,(1080-img.width*scale)/2,400+(650-img.height*scale)/2,img.width*scale,img.height*scale);
      ctx.fillStyle='#e4fd97';let lines=[],fontSize=54;do{ctx.font='bold '+fontSize+'px Vazirmatn';lines=[];let line='';for(const word of d.name.split(' ')){const candidate=line?line+' '+word:word;if(ctx.measureText(candidate).width>900&&line){lines.push(line);line=word;}else line=candidate;}if(line)lines.push(line);if(lines.length<=4)break;fontSize-=4;}while(fontSize>26);let y=1230;for(const line of lines.slice(0,4)){ctx.fillText(line,1000,y,900);y+=fontSize*1.45;}y+=35;
      ctx.fillStyle='#c3daec';ctx.font='34px Vazirmatn';ctx.fillText(d.category,1000,Math.min(y,1530),900);ctx.font='28px Vazirmatn';ctx.fillText('کد کالا: '+d.code,1000,1590,900);
      ctx.fillStyle='#e4fd97';ctx.font='bold 42px Vazirmatn';const price=document.querySelector('[data-story-show-price]').checked;ctx.fillText(price?digits.format(Number(d.price))+' ریال':'برای سفارش با ما تماس بگیرید',1000,1690,920);
      ctx.fillStyle='#d4eaff';ctx.font='34px Vazirmatn';ctx.fillText(d.phone||d.shop,1000,1790,920);
      const blob=await new Promise(resolve=>canvas.toBlob(resolve,'image/png'));if(!blob)throw new Error();const url=URL.createObjectURL(blob);const link=document.createElement('a');link.href=url;link.download='sabzi-story-'+d.code+'.png';link.click();setTimeout(()=>URL.revokeObjectURL(url),5000);status.textContent='استوری آماده و دانلود شد.';
    }catch{status.textContent='ساخت تصویر انجام نشد؛ بارگذاری عکس محصول را بررسی کنید.';}finally{button.disabled=false;}
  }));
})();
