function autoRefreshIfGenerating() {
  if (document.querySelector(".badge.gen")) {
    setTimeout(() => window.location.reload(), 15000);
  }
}

function initNovelPage() {
  const header = document.querySelector(".novel-header");
  if (!header) return;
  const novelId = header.dataset.novelId;
  const generating = header.dataset.generating === "true";

  function setMsg(elId, text, type) {
    const el = document.getElementById(elId);
    if (!el) return;
    el.textContent = text || "";
    el.className = "save-msg" + (type ? " " + type : "");
  }

  async function patchNovel(payload) {
    const res = await fetch(`/api/novels/${novelId}`, {
      method: "PATCH",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(payload),
    });
    if (!res.ok) {
      const data = await res.json().catch(() => ({}));
      throw new Error(data.detail || ("保存失败: " + res.status));
    }
    return res.json();
  }

  // ── Continue now ──────────────────────────
  const continueBtn = document.getElementById("continue-btn");
  if (continueBtn) {
    continueBtn.addEventListener("click", async () => {
      continueBtn.disabled = true;
      setMsg("action-msg", "已请求续写，生成中…");
      try {
        const res = await fetch(`/api/novels/${novelId}/continue`, { method: "POST" });
        if (res.status === 409) {
          setMsg("action-msg", "正在生成中，请稍候。", "err");
          continueBtn.disabled = false;
          return;
        }
        if (!res.ok) throw new Error("续写请求失败: " + res.status);
        setMsg("action-msg", "生成中，稍后自动刷新…");
        setTimeout(() => window.location.reload(), 2000);
      } catch (err) {
        setMsg("action-msg", err.message, "err");
        continueBtn.disabled = false;
      }
    });
  }

  // ── Save provider / auto-continue settings ──
  const saveSettingsBtn = document.getElementById("save-settings-btn");
  if (saveSettingsBtn) {
    saveSettingsBtn.addEventListener("click", async () => {
      const payload = {
        auto_continue: document.getElementById("auto-toggle").checked,
        interval_minutes: parseInt(document.getElementById("interval-input").value || "360", 10),
        provider: document.getElementById("provider-select").value,
        model: document.getElementById("model-input").value.trim() || null,
      };
      setMsg("settings-msg", "保存中…");
      try {
        await patchNovel(payload);
        setMsg("settings-msg", "已保存。", "ok");
      } catch (err) {
        setMsg("settings-msg", err.message, "err");
      }
    });
  }

  // ── Save story content (title / genre / style / premise / settings) ──
  const saveStoryBtn = document.getElementById("save-story-btn");
  if (saveStoryBtn) {
    saveStoryBtn.addEventListener("click", async () => {
      const title = document.getElementById("edit-title").value.trim();
      if (!title) { setMsg("story-msg", "标题不能为空。", "err"); return; }
      const payload = {
        title,
        genre:    document.getElementById("edit-genre").value.trim(),
        style:    document.getElementById("edit-style").value.trim(),
        premise:  document.getElementById("edit-premise").value.trim(),
        settings: document.getElementById("edit-settings").value.trim(),
      };
      setMsg("story-msg", "保存中…");
      try {
        const updated = await patchNovel(payload);
        document.title = updated.title + " · 小说生成器";
        document.querySelector(".novel-header h1").textContent = updated.title;
        setMsg("story-msg", "已保存。", "ok");
      } catch (err) {
        setMsg("story-msg", err.message, "err");
      }
    });
  }

  // ── Save outline ──────────────────────────
  const saveOutlineBtn = document.getElementById("save-outline-btn");
  if (saveOutlineBtn) {
    saveOutlineBtn.addEventListener("click", async () => {
      const payload = { outline: document.getElementById("edit-outline").value };
      setMsg("outline-msg", "保存中…");
      try {
        await patchNovel(payload);
        setMsg("outline-msg", "已保存。", "ok");
      } catch (err) {
        setMsg("outline-msg", err.message, "err");
      }
    });
  }

  // ── Delete ────────────────────────────────
  const deleteBtn = document.getElementById("delete-btn");
  if (deleteBtn) {
    deleteBtn.addEventListener("click", async () => {
      if (!confirm("确定删除这部小说及其所有章节？此操作不可恢复。")) return;
      try {
        const res = await fetch(`/api/novels/${novelId}`, { method: "DELETE" });
        if (!res.ok) throw new Error("删除失败: " + res.status);
        window.location.href = "/";
      } catch (err) {
        setMsg("settings-msg", err.message, "err");
      }
    });
  }

  // ── Poll while generating ─────────────────
  if (generating) pollUntilDone(novelId);
}

async function pollUntilDone(novelId) {
  const poll = async () => {
    try {
      const res = await fetch(`/api/novels/${novelId}`);
      if (!res.ok) return;
      const novel = await res.json();
      if (!novel.is_generating) { window.location.reload(); return; }
    } catch (_) {}
    setTimeout(poll, 8000);
  };
  setTimeout(poll, 8000);
}
