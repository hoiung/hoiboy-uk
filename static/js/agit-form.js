// Progressive-enhancement for the AGIT "Get featured" form.
// The submission POST can take 10-20s (photo upload + email send), and a plain
// form gives no feedback during that wait, so people click Send repeatedly and
// fire duplicate submissions. This locks the button on the first valid submit,
// shows a "Sending..." spinner, and nudges the user if the Turnstile check is
// not done yet. No inline script (CSP is script-src 'self'); loaded via
// <script src="/js/agit-form.js" defer>.
(function () {
  "use strict";

  var form = document.querySelector(".agit-form-wrap form");
  if (!form) return;

  var btn = form.querySelector('button[type="submit"]');
  var submitting = false;

  function showNotice(msg) {
    var el = form.querySelector(".agit-notice");
    if (!el) {
      el = document.createElement("p");
      el.className = "agit-notice";
      el.setAttribute("role", "alert");
      var anchor = btn ? btn.parentNode : null; // the button's .agit-field wrapper
      form.insertBefore(el, anchor);
    }
    el.textContent = msg;
  }

  form.addEventListener("submit", function (e) {
    // Native HTML validation runs before this handler fires, so an invalid
    // (empty required field) form never reaches here and the button is not
    // locked prematurely.

    // Block repeat submits (double-click, Enter mashing) while one is in flight.
    if (submitting) {
      e.preventDefault();
      return;
    }

    // Require the Turnstile token client-side so the user gets an inline nudge
    // instead of a server-side 403 after a long wait.
    var tsField = form.querySelector('[name="cf-turnstile-response"]');
    if (!tsField || !tsField.value) {
      e.preventDefault();
      showNotice("Please complete the verification check just above the button, then hit Send.");
      return;
    }

    // Good to go: lock it and show progress. The page navigates away on the
    // response (303 to /thanks/, or the error page), so no reset is needed.
    submitting = true;
    form.setAttribute("aria-busy", "true");
    if (btn) {
      btn.disabled = true;
      btn.classList.add("is-sending");
      var spinner = document.createElement("span");
      spinner.className = "agit-spinner";
      spinner.setAttribute("aria-hidden", "true");
      btn.textContent = "";
      btn.appendChild(spinner);
      btn.appendChild(document.createTextNode("Sending your story..."));
    }
  });
})();
