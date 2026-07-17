// Interacciones ligeras: copiar al portapapeles, toast y pestañas de código.
(function () {
  'use strict';

  const toast = document.getElementById('copy-toast');
  let toastTimer = null;

  function showToast(message) {
    if (!toast) return;
    toast.textContent = message;
    toast.classList.add('is-visible');
    clearTimeout(toastTimer);
    toastTimer = setTimeout(() => toast.classList.remove('is-visible'), 1800);
  }

  async function copyText(text) {
    try {
      await navigator.clipboard.writeText(text);
      showToast('Copiado al portapapeles');
    } catch (err) {
      showToast('No se pudo copiar');
    }
  }

  // Botones con data-copy (comando de instalación, etc.)
  document.querySelectorAll('[data-copy]').forEach((btn) => {
    btn.addEventListener('click', () => copyText(btn.getAttribute('data-copy') || ''));
  });

  // Pestañas del workbench de código
  const codeData = window.__LEGAL_EXPAND_CODE__ || {};
  const codeSample = document.getElementById('code-sample');
  const codeFilename = document.getElementById('code-filename');
  const codeTabs = document.querySelectorAll('[data-code]');

  codeTabs.forEach((tab) => {
    tab.addEventListener('click', () => {
      const key = tab.getAttribute('data-code');
      const entry = codeData[key];
      if (!entry) return;
      codeTabs.forEach((t) => t.setAttribute('aria-selected', String(t === tab)));
      if (codeSample) codeSample.textContent = entry.code;
      if (codeFilename) codeFilename.textContent = entry.file;
    });
  });

  const copyCodeBtn = document.getElementById('copy-code');
  if (copyCodeBtn && codeSample) {
    copyCodeBtn.addEventListener('click', () => copyText(codeSample.textContent || ''));
  }

  // Exponer helpers para el script de la demo
  window.__legalExpandUI = { showToast, copyText };
})();
