// Progressive enhancement for the newsletter subscribe form (#56 Stage 5).
//
// Without this, every non-happy path is a bare text/plain page: no navigation,
// no way back, and the name and email the reader typed are gone. That is not a
// corner case reached only by bots. The Turnstile script is loaded `async
// defer`, so anyone who fills two short fields and submits before it resolves
// gets a guaranteed 403, as does anyone whose network blocks
// challenges.cloudflare.com. The form renders on ~346 pages.
//
// The repo already ships this idea for the AGIT form (static/js/agit-form.js);
// this is the same pattern for the second form, not a new invention.
//
// PROGRESSIVE, not required. With JavaScript off the form is a plain HTML POST
// and behaves exactly as it did before this file existed. Everything here is an
// improvement layered on top, never a precondition. No inline script: the CSP is
// script-src 'self', and this loads from static/ with a content-hash query so a
// stale copy cannot outlive a deploy (see the partial that emits the tag).
(function () {
  "use strict";

  // Where a successful subscribe lands. Kept in step with CHECK_INBOX_PATH in
  // functions/api/subscribe.js -- only used as a fallback, because the response
  // normally carries its own URL after following the 303.
  var CHECK_INBOX_PATH = "/newsletter/check-inbox/";

  // What the reader is told when the endpoint fails. Keyed by status, because
  // the endpoint's own text/plain bodies are written for the same situations and
  // there is no reason to say something different here. An unlisted status falls
  // back to the generic line rather than surfacing a raw upstream body.
  function messageFor(status) {
    if (status === 403) {
      return "The verification check did not pass. Please complete it just above " +
             "the button and try again.";
    }
    if (status === 413) return "That submission is too large.";
    if (status === 429 || status === 503) {
      return "We are sending a lot of email right now. Please try again in a few minutes.";
    }
    if (status === 400) {
      return "Please check your name and email address, then try again.";
    }
    if (status >= 500) {
      return "Something went wrong signing you up. Please try again in a moment.";
    }
    return "Something went wrong signing you up. Please try again.";
  }

  // Test surface, declared BEFORE any DOM access so `require()` from node --test
  // works in bare Node with no document. Under jsdom the module wrapper is
  // absent, so the browser path below runs and the DOM tests drive the shipped
  // code rather than a hand-mirrored copy of it. Same arrangement as
  // static/js/agit-form.js.
  if (typeof module !== "undefined" && module.exports) {
    module.exports = { messageFor: messageFor, CHECK_INBOX_PATH: CHECK_INBOX_PATH };
  }
  if (typeof document === "undefined") return;

  var form = document.querySelector(".subscribe-form form");
  if (!form) return;

  // fetch is what lets a failure stay on THIS page with the fields intact. Where
  // it is missing, do nothing at all and let the browser submit natively: the
  // old bare-text-page behaviour is worse, but it still subscribes people, and a
  // half-enhanced form that swallows the submit would not.
  if (typeof window.fetch !== "function") return;

  var btn = form.querySelector('button[type="submit"]');
  var submitting = false;
  var originalLabel = btn ? btn.textContent : "";

  function showNotice(msg) {
    var el = form.querySelector(".subscribe-notice");
    if (!el) {
      el = document.createElement("p");
      el.className = "subscribe-notice";
      // role=alert so a screen reader announces it without moving focus, which
      // would yank the reader away from the field they are fixing.
      el.setAttribute("role", "alert");
      var anchor = btn ? btn.parentNode : null; // the button's .subscribe-field
      form.insertBefore(el, anchor);
    }
    el.textContent = msg;
    return el;
  }

  function clearNotice() {
    var el = form.querySelector(".subscribe-notice");
    if (el) el.textContent = "";
  }

  function unlock() {
    submitting = false;
    form.removeAttribute("aria-busy");
    if (btn) {
      btn.disabled = false;
      btn.textContent = originalLabel;
    }
    // A Turnstile token is SINGLE USE. Without this reset the next attempt
    // re-sends a spent token and earns a second 403, so the reader is stuck in a
    // loop the first failure put them in.
    if (window.turnstile && typeof window.turnstile.reset === "function") {
      try {
        window.turnstile.reset();
      } catch (err) {
        /* A reset failure must not take the form down with it. */
      }
    }
  }

  form.addEventListener("submit", function (e) {
    // Native HTML validation runs before this handler, so a form with an empty
    // required field never reaches here and the button is not locked early.

    if (submitting) {
      e.preventDefault();
      return;
    }

    // The common failure, caught before the round trip: the widget has not
    // resolved yet (it loads async) or was blocked, so there is no token and the
    // server would answer 403. An inline nudge beats a blank page.
    var tsField = form.querySelector('[name="cf-turnstile-response"]');
    if (!tsField || !tsField.value) {
      e.preventDefault();
      showNotice(
        "The verification check has not finished loading yet. Give it a moment, " +
        "then hit Subscribe again."
      );
      return;
    }

    e.preventDefault();
    clearNotice();
    submitting = true;
    form.setAttribute("aria-busy", "true");
    if (btn) {
      btn.disabled = true;
      btn.textContent = "Subscribing...";
    }

    window.fetch(form.action, {
      method: "POST",
      body: new FormData(form),
      // Same-origin credentials and redirect-follow so the 303 to the
      // check-inbox page resolves here and can be read off the response.
      credentials: "same-origin",
      redirect: "follow",
    }).then(function (resp) {
      if (resp.ok || resp.redirected) {
        window.location.assign(resp.url || CHECK_INBOX_PATH);
        return;
      }
      showNotice(messageFor(resp.status));
      unlock();
    }).catch(function () {
      // Offline, DNS failure, request blocked. The fields are still filled in,
      // which is the whole point of handling this here.
      showNotice(
        "We could not reach the server. Check your connection and try again."
      );
      unlock();
    });
  });
})();
