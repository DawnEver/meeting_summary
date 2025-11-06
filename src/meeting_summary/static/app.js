// Shared front-end logic for Meeting Toolkit (ZH/EN)
// Provide localized strings via initApp(strings)

(function(){
  function $(id){ return document.getElementById(id); }

  function setText(el, v){ if(el) el.textContent = v; }
  function setHTML(el, v){ if(el) el.innerHTML = v; }

  async function postJSON(url, body){
    const r = await fetch(url, { method:'POST', headers:{'Content-Type':'application/json'}, body: JSON.stringify(body) });
    const j = await r.json().catch(()=>({}));
    if(!r.ok){ throw new Error(j.description || j.detail || String(r.status)); }
    return j;
  }

  async function postForm(url, fd){
    const r = await fetch(url, { method:'POST', body: fd });
    const j = await r.json().catch(()=>({}));
    if(!r.ok){ throw new Error(j.description || j.detail || String(r.status)); }
    return j;
  }

  function initApp(strings){
    // Step 1: Video -> Audio
    const btnVideo2Audio = $('btnVideo2Audio');
    if(btnVideo2Audio){
      btnVideo2Audio.addEventListener('click', async ()=>{
        const f = $('videoFile')?.files?.[0];
        if(!f){ alert(strings.alertChooseVideo); return; }
        const fd = new FormData();
        fd.append('video', f);
        setText($('audioResult'), strings.convertingText);
        try {
          const j = await postForm('/api/video-to-audio', fd);
          setHTML($('audioResult'), `${strings.audioIdLabel}: <span class="mono">${j.audio_id}</span> | <a href="${j.download_url}" target="_blank">${strings.downloadLabel}</a>`);
          if($('audioId')) $('audioId').value = j.audio_id;
        } catch(err){ setText($('audioResult'), `${strings.errorPrefix} ${err.message}`); }
      });
    }

    // Step 2: Audio -> Transcript
    const btnAudio2Text = $('btnAudio2Text');
    if(btnAudio2Text){
      btnAudio2Text.addEventListener('click', async ()=>{
        const fd = new FormData();
        const f = $('audioFile')?.files?.[0];
        const audioId = ($('audioId')?.value || '').trim();
        if(f){ fd.append('audio', f); }
        else if(audioId){ fd.append('audio_id', audioId); }
        else { alert(strings.chooseAudioOrIdAlert); return; }
        setText($('transcript'), strings.transcribingText);
        try {
          const j = await postForm('/api/audio-to-transcript', fd);
          setText($('transcript'), j.transcript || '');
        } catch(err){ setText($('transcript'), `${strings.errorPrefix} ${err.message}`); }
      });
    }

    // Step 3: Transcript -> Summary
    const btnSummarize = $('btnSummarize');
    if(btnSummarize){
      btnSummarize.addEventListener('click', async ()=>{
        const transcript = ($('transcriptForSummary')?.value || '').trim();
        if(!transcript){ alert(strings.transcriptEmptyAlert); return; }
        setText($('summary'), strings.summarizingText);
        const payload = {
          transcript,
          ollama_model: $('model')?.value || 'qwen3:30b-a3b',
          context_length: Number($('ctxLen')?.value || 0),
          extra_prompt: $('extraPrompt')?.value || null
        };
        try {
          const j = await postJSON('/api/summarize', payload);
          setText($('summary'), j.summary || '');
        } catch(err){ setText($('summary'), `${strings.errorPrefix} ${err.message}`); }
      });
    }

    const btnCopy = $('btnCopyFromS2');
    if(btnCopy){ btnCopy.addEventListener('click', ()=>{ if($('transcriptForSummary')) $('transcriptForSummary').value = $('transcript')?.value || ''; }); }

    // One-click with progress via SSE
    const btnPipelineSSE = $('btnOneClickStream');
    if(btnPipelineSSE){
      btnPipelineSSE.addEventListener('click', async ()=>{
        const f = $('videoAll')?.files?.[0];
        if(!f){ alert(strings.alertChooseVideo); return; }
        const fd = new FormData();
        fd.append('video', f);
        fd.append('whisper_model', $('whisperModelAll')?.value || 'turbo');
        fd.append('ollama_model', $('modelAll')?.value || 'qwen3:30b-a3b');
        fd.append('context_length', $('ctxLenAll')?.value || '0');
        fd.append('extra_prompt', $('extraPromptAll')?.value || '');
        setText($('pipelineAudioLink'), strings.startingText);
        setText($('pipelineLog'), '');
        setText($('pipelineTranscript'), '');
        setText($('pipelineSummary'), '');
        try {
          const j = await postForm('/api/pipeline/start', fd);
          const jobId = j.job_id;
          setText($('pipelineLog'), `${strings.jobStartedPrefix} ${jobId}\n`);
          const es = new EventSource(`/api/pipeline/events/${jobId}`);
          es.onmessage = (ev)=>{
            try{
              const data = JSON.parse(ev.data);
              if(data.type === 'done'){
                es.close();
                if(data.error){
                  $('pipelineLog').textContent += `[error] ${data.error}\n`;
                } else if(data.result){
                  const r = data.result;
                  setHTML($('pipelineAudioLink'), `${strings.audioIdLabel}: <span class="mono">${r.audio_id}</span> | <a href="${r.download_url}" target="_blank">${strings.downloadLabel}</a>`);
                  setText($('pipelineTranscript'), r.transcript || '');
                  setText($('pipelineSummary'), r.summary || '');
                  if($('audioId')) $('audioId').value = r.audio_id || '';
                  if($('transcript')) $('transcript').value = r.transcript || '';
                  if($('transcriptForSummary')) $('transcriptForSummary').value = r.transcript || '';
                  setText($('summary'), r.summary || '');
                }
                return;
              }
              $('pipelineLog').textContent += `[${data.type}] ${data.text}\n`;
            }catch(_){ /* ignore */ }
          };
          es.onerror = ()=>{ $('pipelineLog').textContent += `[error] ${strings.connectionLostText}\n`; es.close(); };
        } catch(err){ setText($('pipelineAudioLink'), `${strings.errorPrefix} ${err.message}`); }
      });
    }
  }

  // expose
  window.initMeetingApp = { initApp };
})();
