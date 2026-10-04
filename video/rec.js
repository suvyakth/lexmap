/* Lexmap video recorder.
 * Each video page calls Rec.init({...}) with a GSAP timeline builder and timed narration cues.
 * "Render" captures this tab with getDisplayMedia (cropped to #stage when Region Capture is available),
 * optionally mixes in the microphone, and saves an MP4 (WebM if the browser cannot record MP4).
 * Nothing is installed or uploaded: the file is written by the browser to Downloads. */
(function () {
  "use strict";
  const $ = (s) => document.querySelector(s);
  const fmt = (s) => `${Math.floor(s / 60)}:${String(Math.floor(s % 60)).padStart(2, "0")}`;
  const wait = (ms) => new Promise((r) => setTimeout(r, ms));

  const Rec = {};
  let opt, tl, stage, prompter = null, camStream = null, cueIdx = -1;

  function fit() {
    const s = Math.min(innerWidth / 1920, innerHeight / 1080);
    stage.style.transform = `translate(-50%, -50%) scale(${s})`;
  }

  function status(msg) { $("#ctl .status").textContent = msg; }

  // ---------------------------------------------------------------- captions + teleprompter
  function showCue(i) {
    cueIdx = i;
    const c = opt.cues[i];
    const cap = $("#captions");
    if (!c || !c.say) { cap.innerHTML = ""; } else { cap.innerHTML = `<span>${c.say}</span>`; }
    if (window.gsap && c && c.say) gsap.fromTo(cap, { opacity: 0, y: 12 }, { opacity: 1, y: 0, duration: .35, ease: "power2.out" });
    updatePrompter();
  }

  function openPrompter() {
    if (prompter && !prompter.closed) { prompter.focus(); return; }
    prompter = window.open("", "lexmap-prompter", "width=900,height=420,left=40,top=40");
    if (!prompter) { status("Popup blocked: allow popups for localhost to use the teleprompter."); return; }
    prompter.document.write(`<!doctype html><title>Teleprompter</title>
      <style>body{margin:0;background:#0b1215;color:#eef3f2;font:600 30px/1.45 Inter,system-ui,sans-serif;padding:22px 30px}
      #t{font:600 18px ui-monospace,Consolas,monospace;color:#2dd4bf}#bar{height:6px;background:#24363e;border-radius:3px;margin:8px 0 18px}
      #bar i{display:block;height:100%;width:0;background:#2dd4bf;border-radius:3px}#now{color:#fff}#next{color:#6f8288;font-size:24px;margin-top:22px}
      #note{font:14px system-ui;color:#6f8288;position:fixed;bottom:10px;left:30px}</style>
      <div id="t">ready</div><div id="bar"><i></i></div><div id="now">Press Preview or Render in the main window.</div><div id="next"></div>
      <div id="note">This window is not recorded. Keep it from fully covering the video tab.</div>`);
    prompter.document.close();
    updatePrompter();
  }

  function updatePrompter() {
    if (!prompter || prompter.closed) return;
    const d = prompter.document, c = opt.cues[cueIdx], n = opt.cues[cueIdx + 1];
    d.getElementById("now").textContent = c ? (c.say || "(pause)") : "";
    d.getElementById("next").textContent = n ? `next (${fmt(n.t)}): ${n.say || ""}` : "";
  }

  function tickPrompter() {
    if (!prompter || prompter.closed || !tl) return;
    const d = prompter.document, t = tl.time();
    d.getElementById("t").textContent = `${fmt(t)} / ${fmt(opt.duration)}`;
    d.getElementById("bar").firstElementChild.style.width = `${(100 * t / opt.duration).toFixed(1)}%`;
  }

  // ---------------------------------------------------------------- timeline
  async function build() {
    if (tl) tl.kill();
    gsap.globalTimeline.getChildren().forEach((c) => c.kill());
    showCue(-1);
    if (opt.prepare) { status("Preparing…"); await opt.prepare(); }
    tl = gsap.timeline({ paused: true });
    opt.build(tl, stage);
    opt.cues.forEach((c, i) => tl.call(showCue, [i], c.t));
    tl.set({}, {}, opt.duration); // pad to exact duration
    tl.eventCallback("onUpdate", () => {
      tickPrompter();
      const r = $("#scrub"); if (r && document.activeElement !== r) r.value = tl.time();
    });
    status(`Ready · ${opt.duration}s`);
  }

  async function preview() {
    $("#play").disabled = true;
    await build();
    tl.play(0);
    tl.eventCallback("onComplete", () => { $("#play").disabled = false; status("Preview finished."); });
  }

  // ---------------------------------------------------------------- recording
  function pickMime(withAudio) {
    const list = withAudio
      ? ["video/mp4;codecs=avc1.640028,mp4a.40.2", "video/mp4;codecs=avc1,mp4a.40.2", "video/mp4", "video/webm;codecs=vp9,opus", "video/webm"]
      : ["video/mp4;codecs=avc1.640028", "video/mp4;codecs=avc1", "video/mp4", "video/webm;codecs=vp9", "video/webm"];
    return list.find((m) => window.MediaRecorder && MediaRecorder.isTypeSupported(m)) || "";
  }

  async function countdown() {
    const el = $("#countdown");
    el.style.display = "grid";
    for (const n of [3, 2, 1]) {
      el.textContent = n;
      if (prompter && !prompter.closed) prompter.document.getElementById("now").textContent = `Starting in ${n}…  First line: ${opt.cues[0] ? opt.cues[0].say : ""}`;
      await wait(1000);
    }
    el.style.display = "none";
    await new Promise((r) => requestAnimationFrame(() => requestAnimationFrame(r)));
  }

  async function render() {
    const narrate = $("#narrate").checked;
    let display, mic;
    try {
      display = await navigator.mediaDevices.getDisplayMedia({
        video: { frameRate: { ideal: 30, max: 30 }, cursor: "never" }, audio: false,
        preferCurrentTab: true, selfBrowserSurface: "include", surfaceSwitching: "exclude", monitorTypeSurfaces: "exclude",
      });
    } catch (e) { status("Screen capture was cancelled."); return; }
    const vtrack = display.getVideoTracks()[0];
    let cropped = false;
    try {
      if (window.CropTarget && vtrack.cropTo) { await vtrack.cropTo(await CropTarget.fromElement(stage)); cropped = true; }
    } catch (e) { /* fall back to full tab */ }
    if (narrate) {
      try { mic = await navigator.mediaDevices.getUserMedia({ audio: { echoCancellation: true, noiseSuppression: true, autoGainControl: true } }); }
      catch (e) { status("Microphone was blocked, so this render is silent."); }
    }
    const tracks = [vtrack].concat(mic ? mic.getAudioTracks() : []);
    const mime = pickMime(!!mic);
    const ext = mime.startsWith("video/mp4") ? "mp4" : "webm";

    document.body.classList.add("recording");
    fit();
    await build();
    if (narrate && $("#tele").checked) openPrompter();
    await countdown();

    const chunks = [];
    const rec = new MediaRecorder(new MediaStream(tracks), { mimeType: mime || undefined, videoBitsPerSecond: 12_000_000, audioBitsPerSecond: 160_000 });
    rec.ondataavailable = (e) => { if (e.data && e.data.size) chunks.push(e.data); };
    const done = new Promise((r) => { rec.onstop = r; });
    rec.start(1000);
    tl.play(0);
    await new Promise((r) => tl.eventCallback("onComplete", r));
    await wait(400);
    rec.stop();
    await done;
    display.getTracks().forEach((t) => t.stop());
    if (mic) mic.getTracks().forEach((t) => t.stop());
    document.body.classList.remove("recording");

    const blob = new Blob(chunks, { type: mime || "video/webm" });
    const url = URL.createObjectURL(blob);
    const name = `lexmap-${opt.slug}-${mic ? "voice" : "silent"}.${ext}`;
    const a = document.createElement("a");
    a.href = url; a.download = name; document.body.appendChild(a); a.click(); a.remove();
    $("#out").innerHTML = `<video src="${url}" controls></video><p>Saved <b>${name}</b> (${(blob.size / 1e6).toFixed(1)} MB) to Downloads. <a href="${url}" download="${name}">Download again</a></p>`;
    const v = $("#out video");
    v.onloadedmetadata = () => status(`Done: ${name}\nformat ${mime || "default"}${cropped ? "" : "\n(not cropped: full tab captured)"}\nlength ${isFinite(v.duration) ? v.duration.toFixed(1) + "s" : "see file"}`);
    if (ext !== "mp4") status(`Saved ${name}. This browser could not record MP4. Google Drive and YouTube accept WebM.`);
  }

  // ---------------------------------------------------------------- webcam
  async function toggleCam(on) {
    if (on) {
      try {
        camStream = await navigator.mediaDevices.getUserMedia({ video: { width: 1280, height: 720 } });
        $("#cam video").srcObject = camStream;
        document.body.classList.add("with-cam");
      } catch (e) { $("#camchk").checked = false; status("Camera was blocked."); }
    } else {
      document.body.classList.remove("with-cam");
      if (camStream) camStream.getTracks().forEach((t) => t.stop());
      camStream = null;
    }
  }

  // ---------------------------------------------------------------- UI
  Rec.init = function (o) {
    opt = Object.assign({ duration: 58, cues: [], scrub: true, camDefault: false }, o);
    stage = $("#stage");
    stage.insertAdjacentHTML("beforeend", `<div id="captions"></div><div id="cam"><video autoplay muted playsinline></video></div><div id="countdown"></div>`);
    document.body.insertAdjacentHTML("beforeend", `
      <div id="ctl">
        <button class="min" title="Collapse">–</button>
        <h1>${opt.title}</h1>
        <p>${opt.help || ""}</p>
        <div class="row">
          <button id="play">▶ Preview</button>
          <button id="tp">Teleprompter</button>
          <button id="rec" class="primary">● Render MP4</button>
        </div>
        ${opt.scrub ? `<input id="scrub" type="range" min="0" max="${opt.duration}" step="0.05" value="0">` : ""}
        <label><input type="checkbox" id="caps" checked> Burned-in captions</label>
        <label><input type="checkbox" id="narrate"> Record my voice while rendering (mic)</label>
        <label><input type="checkbox" id="tele" checked> …and open the teleprompter window</label>
        <label><input type="checkbox" id="camchk"> Webcam bubble</label>
        <p>Before rendering: press <b>F11</b> for full screen (sharper video). When Edge asks what to share, pick <b>this tab</b>.</p>
        <div class="status"></div>
        <div id="out"></div>
        <p><a href="index.html">← all videos</a></p>
      </div>`);
    fit();
    addEventListener("resize", fit);
    $("#play").onclick = preview;
    $("#rec").onclick = render;
    $("#tp").onclick = openPrompter;
    $("#caps").onchange = (e) => document.body.classList.toggle("no-captions", !e.target.checked);
    $("#camchk").onchange = (e) => toggleCam(e.target.checked);
    $("#ctl .min").onclick = () => $("#ctl").classList.toggle("collapsed");
    if (opt.scrub) {
      $("#scrub").oninput = async (e) => {
        if (!tl) await build();
        tl.pause();
        const t = +e.target.value;
        tl.seek(t, false);
        let i = -1; opt.cues.forEach((c, k) => { if (c.t <= t) i = k; }); showCue(i);
        $("#play").disabled = false;
      };
    }
    gsap.ticker.lagSmoothing(0); // keep timeline time equal to wall-clock time, so narration stays in sync
    if (opt.camDefault) { $("#camchk").checked = false; }
    const mime = pickMime(false);
    status(mime.startsWith("video/mp4") ? "This browser records MP4." : mime ? "This browser records WebM only." : "This browser cannot record video.");
    build();
  };

  window.Rec = Rec;
})();
