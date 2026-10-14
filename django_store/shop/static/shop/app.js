// Progressive enhancement: everything works without JS; JS adds instant cart updates and toasts.
(function () {
  const toasts = document.getElementById("toasts");
  function toast(msg, kind) {
    const t = document.createElement("div");
    t.className = "toast " + (kind || "");
    t.textContent = msg;
    toasts.appendChild(t);
    fade(t);
  }
  function fade(t) {
    setTimeout(() => t.classList.add("hide"), 2600);
    setTimeout(() => t.remove(), 3100);
  }
  document.querySelectorAll("#toasts .toast").forEach(fade);

  document.querySelectorAll("form.add-form").forEach((form) => {
    form.addEventListener("submit", async (e) => {
      e.preventDefault();
      const btn = form.querySelector("button");
      btn.disabled = true;
      try {
        const res = await fetch(form.action, {
          method: "POST",
          body: new FormData(form),
          headers: { "X-Requested-With": "fetch" },
        });
        if (res.redirected && res.url.includes("/accounts/login/")) {
          window.location = res.url;
          return;
        }
        const data = await res.json();
        document.getElementById("cart-count").textContent = data.cart_count;
        toast(data.message, data.ok ? "success" : "error");
      } catch (err) {
        form.submit();
      } finally {
        btn.disabled = false;
      }
    });
  });

  document.querySelectorAll("form[data-confirm]").forEach((form) => {
    form.addEventListener("submit", (e) => {
      if (!confirm(form.dataset.confirm)) e.preventDefault();
    });
  });
})();
