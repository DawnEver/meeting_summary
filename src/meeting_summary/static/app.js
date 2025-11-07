// Shared front-end logic for Meeting Toolkit (ZH/EN)
// Provide localized strings via initApp(strings)

(function(){
  function $(id){ return document.getElementById(id); }

  function setText(el, v){ if(el) el.textContent = v; }
  function setHTML(el, v){ if(el) el.innerHTML = v; }

  // Minimal, safe markdown renderer for summary display.
  // Supports: code blocks, inline code, headers, bold, italic, links, unordered lists, paragraphs.
  function escapeHtml(s){
    return String(s).replace(/&/g,'&amp;').replace(/</g,'&lt;').replace(/>/g,'&gt;');
  }

  function renderMarkdown(md, isInner = false){
    if(!md) return '';
    md = String(md).replace(/\r\n/g,'\n');

    // If the consumer has vendored `marked` (CommonMark) into `static/marked.min.js`,
    // prefer that for full CommonMark support. If `DOMPurify` is present, sanitize
    // the generated HTML to reduce XSS risk. This keeps a safe fallback to the
    // lightweight renderer when `marked` is not available.
    try {
      if (typeof window !== 'undefined' && window.marked && typeof window.marked.parse === 'function') {
        let html = window.marked.parse(md);
        if (typeof window.DOMPurify !== 'undefined' && typeof window.DOMPurify.sanitize === 'function') {
          try { html = window.DOMPurify.sanitize(html); } catch (_) { /* ignore sanitize errors */ }
        }
        return html;
      }
    } catch (_) { /* ignore and fall back */ }

    // Extract fenced code blocks first
    const codeBlocks = [];
    md = md.replace(/```([\s\S]*?)```/g, function(_, code){
      codeBlocks.push(code);
      return `___CODEBLOCK_${codeBlocks.length-1}___`;
    });

    // Handle blockquotes and horizontal rules only at top-level (not inside nested calls)
    const blockQuotes = [];
    if(!isInner){
      // Blockquotes: contiguous lines starting with '>'
      md = md.replace(/(^>(?:[^\n]*\n?)+)/gm, function(block){
        // remove leading '> ' from each line
        const inner = block.split('\n').map(l=>l.replace(/^>\s?/, '')).join('\n');
        // render inner content recursively but mark as inner to avoid infinite recursion
        const rendered = renderMarkdown(inner, true);
        blockQuotes.push(rendered);
        return `___BLOCKQUOTE_${blockQuotes.length-1}___`;
      });

      // Horizontal rules: lines that are --- or *** or ___
      md = md.replace(/^\s*(?:---|\*\*\*|___)\s*$/gm, '<hr/>');
    }

    // Escape remaining content
    md = escapeHtml(md);

    // Inline code (backticks)
    md = md.replace(/`([^`]+)`/g, function(_, c){ return '<code>' + escapeHtml(c) + '</code>'; });

    // Links [text](url)
    md = md.replace(/\[([^\]]+)\]\(([^)]+)\)/g, '<a href="$2" target="_blank" rel="noopener noreferrer">$1</a>');

    // Headers
    md = md.replace(/^######\s*(.+)$/gm, '<h6>$1</h6>');
    md = md.replace(/^#####\s*(.+)$/gm, '<h5>$1</h5>');
    md = md.replace(/^####\s*(.+)$/gm, '<h4>$1</h4>');
    md = md.replace(/^###\s*(.+)$/gm, '<h3>$1</h3>');
    md = md.replace(/^##\s*(.+)$/gm, '<h2>$1</h2>');
    md = md.replace(/^#\s*(.+)$/gm, '<h1>$1</h1>');

    // Bold and italics
    md = md.replace(/\*\*(.+?)\*\*/g, '<strong>$1</strong>');
    md = md.replace(/\*(.+?)\*/g, '<em>$1</em>');

    // Unordered lists (blocks of lines starting with - or *)
    md = md.replace(/(?:^|\n)((?:[ \t]*[-*] .+(?:\n|$))+)/g, function(_, block){
      const items = block.trim().split(/\n+/).map(l=>l.replace(/^[ \t]*[-*] /,'').trim());
      return '\n<ul>\n' + items.map(i=>'<li>'+i+'</li>').join('\n') + '\n</ul>\n';
    });

    // Paragraphs: split on two or more newlines
    const parts = md.split(/\n{2,}/g).map(p=>p.trim()).filter(Boolean).map(p=>{
      // leave block-level elements as-is
      if(p.startsWith('<h') || p.startsWith('<ul') || p.startsWith('<pre') || p.startsWith('<blockquote') || p.startsWith('<hr')) return p;
      // convert single newlines into <br>
      return '<p>' + p.replace(/\n/g,'<br>') + '</p>';
    });
    md = parts.join('\n\n');

    // Restore code blocks
    md = md.replace(/___CODEBLOCK_(\d+)___/g, function(_, idx){
      const code = codeBlocks[Number(idx)] || '';
      return '<pre><code>' + escapeHtml(code) + '</code></pre>';
    });

    // Restore blockquotes (rendered HTML stored earlier)
    if(blockQuotes.length){
      md = md.replace(/___BLOCKQUOTE_(\d+)___/g, function(_, idx){
        return '<blockquote>' + (blockQuotes[Number(idx)] || '') + '</blockquote>';
      });
    }

    return md;
  }

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
    // helper: download text as a file
    function downloadTextBlob(filename, text, mime){
      mime = mime || 'text/markdown';
      const blob = new Blob([text || ''], { type: mime });
      const url = URL.createObjectURL(blob);
      const a = document.createElement('a');
      a.href = url;
      a.download = filename;
      document.body.appendChild(a);
      a.click();
      a.remove();
      setTimeout(()=>URL.revokeObjectURL(url), 5000);
    }

    function setDownloadAnchor(id, url, filename){
      const a = $(id);
      if(!a) return;
      if(url){
        a.href = url;
        if(filename) a.setAttribute('download', filename);
        a.style.display = '';
      } else {
        a.style.display = 'none';
      }
    }

    function copyToClipboard(text){
      if(!text) return;
      if(navigator.clipboard && navigator.clipboard.writeText){
        navigator.clipboard.writeText(text).catch(()=>{});
      } else {
        const ta = document.createElement('textarea');
        ta.value = text;
        document.body.appendChild(ta);
        ta.select();
        try{ document.execCommand('copy'); }catch(_){}
        ta.remove();
      }
    }

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
          // show download links if available
          setDownloadAnchor('aDownloadTranscript', j.download_transcript_url || null, (j.audio_id && `${j.audio_id}.transcript.txt`) || 'transcript.txt');
          setDownloadAnchor('aDownloadSRT', j.download_srt_url || null, (j.audio_id && `${j.audio_id}.srt`) || 'subtitles.srt');
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
          const md = j.summary || '';
          setHTML($('summary'), renderMarkdown(md));
          if($('summary')) $('summary').dataset.md = md;
        } catch(err){ setText($('summary'), `${strings.errorPrefix} ${err.message}`); }
      });
    }

    const btnCopy = $('btnCopyFromS2');
    if(btnCopy){ btnCopy.addEventListener('click', ()=>{ if($('transcriptForSummary')) $('transcriptForSummary').value = $('transcript')?.value || ''; }); }

    // Summary copy / download (step 3)
    const btnCopySummary = $('btnCopySummary');
    const btnDownloadSummary = $('btnDownloadSummary');
    if(btnCopySummary){ btnCopySummary.addEventListener('click', ()=>{
      const md = $('summary')?.dataset?.md || '';
      if(!md){ alert(strings.transcriptEmptyAlert); return; }
      copyToClipboard(md);
    }); }
    if(btnDownloadSummary){ btnDownloadSummary.addEventListener('click', ()=>{
      const md = $('summary')?.dataset?.md || '';
      if(!md){ alert(strings.transcriptEmptyAlert); return; }
      downloadTextBlob('summary.md', md, 'text/markdown');
    }); }

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
  setHTML($('pipelineSummary'), '');
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
                  // populate download links area
                  const linksDiv = $('pipelineDownloadLinks');
                  if(linksDiv){
                    linksDiv.innerHTML = '';
                    if(r.download_transcript_url){
                      const a = document.createElement('a');
                      a.className = 'secondary';
                      a.href = r.download_transcript_url;
                      a.target = '_blank';
                      a.textContent = 'Download TXT';
                      linksDiv.appendChild(a);
                    }
                    if(r.download_srt_url){
                      const a2 = document.createElement('a');
                      a2.className = 'secondary';
                      a2.href = r.download_srt_url;
                      a2.target = '_blank';
                      a2.textContent = 'Download SRT';
                      linksDiv.appendChild(a2);
                    }
                  }
                  setHTML($('pipelineSummary'), renderMarkdown(r.summary || ''));
                  if($('pipelineSummary')) $('pipelineSummary').dataset.md = r.summary || '';
                  if($('audioId')) $('audioId').value = r.audio_id || '';
                  if($('transcript')) $('transcript').value = r.transcript || '';
                  if($('transcriptForSummary')) $('transcriptForSummary').value = r.transcript || '';
                  setHTML($('summary'), renderMarkdown(r.summary || ''));
                  if($('summary')) $('summary').dataset.md = r.summary || '';
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

      // Pipeline summary copy / download
      const btnCopyPipelineSummary = $('btnCopyPipelineSummary');
      const btnDownloadPipelineSummary = $('btnDownloadPipelineSummary');
      if(btnCopyPipelineSummary){ btnCopyPipelineSummary.addEventListener('click', ()=>{
        const md = $('pipelineSummary')?.dataset?.md || '';
        if(!md){ alert(strings.transcriptEmptyAlert); return; }
        copyToClipboard(md);
      }); }
      if(btnDownloadPipelineSummary){ btnDownloadPipelineSummary.addEventListener('click', ()=>{
        const md = $('pipelineSummary')?.dataset?.md || '';
        if(!md){ alert(strings.transcriptEmptyAlert); return; }
        downloadTextBlob('pipeline-summary.md', md, 'text/markdown');
      }); }
  }

  // expose
  window.initMeetingApp = { initApp };
})();
