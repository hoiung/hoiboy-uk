---
title: "AGIT Events Signup"
description: "Sign up once to attend AGIT events and get the invite to our WhatsApp community groups. Free."
hideDate: true
# The AGIT page is a leaf bundle and cannot hold a child page, so this sibling
# bundle uses a url override to serve under it, the agit-thanks pattern (#65).
url: "/community/asians-gingers-in-tech/join/"
breadcrumbParent: "/community/asians-gingers-in-tech"
---

<!-- iamhoi -->
You need to sign up to attend our events. You only need to sign up once and become a member of our AGIT community and join our WhatsApp group. This is mandatory.

The membership is free because we're a self-contributing community where members give to build what we have. It's not the usual networking event where you're trying to find a job or sell.
<!-- iamhoi-skip -->
<!-- The sentence below is Hoi's own wording, kept as he wrote it: "facilitating" is his word (#65 R10). -->
Networking is about giving and adding value within our community, and it's free to join and help make it better because this is your community that we're facilitating.
<!-- iamhoi-skipend -->

**Why the WhatsApp invite comes by email.** Our WhatsApp link used to be public on Meetup, and we have been bombarded by crypto and stock bots spamming our groups constantly. So to protect our group, the invite link is sent once you sign up to our form and confirm your email is correct, and then we send you the welcome email.

**Photos and videos at our events.** Attendees to our events may take photos and videos and share them. AGIT's own channels may share them too, but never in adverts. If you'd rather not be in photos, tell us at the event. If you want a photo or video of you taken down from AGIT's channels, email hello@hoiboy.uk and we'll take it down within one month.
<!-- iamhoiend -->

<!-- The form posts to the newsletter endpoint with audience=agit (functions/api/subscribe.js).
     The .subscribe-form wrapper is what static/js/subscribe-form.js binds to; the footer copy
     of that form is suppressed on every AGIT page, so this page loads the script itself.
     The two hidden versions and the newsletter label are pinned by
     tests/test_agit_signup_consent_version.py: the membership version to
     KNOWN_AGIT_CONSENT_VERSIONS, the newsletter label + version to the footer partial.
     The newsletter box is OPTIONAL here: it carries neither checked nor required. -->
<div class="subscribe-form">
<form method="POST" action="/api/subscribe">

  <input type="hidden" name="audience" value="agit">

  <div class="subscribe-field">
    <label for="agit-join-name">Your name</label>
    <input type="text" id="agit-join-name" name="name" maxlength="100" autocomplete="name" required>
  </div>

  <div class="subscribe-field">
    <label for="agit-join-email">Your email</label>
    <input type="email" id="agit-join-email" name="email" maxlength="254" autocomplete="email" required>
  </div>

  <div class="subscribe-hp" aria-hidden="true">
    <input type="text" id="agit-join-website" name="website" tabindex="-1" autocomplete="off">
  </div>

  <div class="subscribe-field subscribe-consent">
    <input type="hidden" name="member_consent_version" value="2026-10-15">
    <input type="checkbox" id="agit-join-member" name="member_consent" required>
    <!-- iamhoi -->
    <label for="agit-join-member">Yes, sign me up as an AGIT member. I agree to you keeping my name and email for my membership, and I agree that attendees to our events may take photos and videos and share them, as explained above. I understand that to attend events I need to be signed up and in the AGIT WhatsApp group, where other members can see my phone number. See the <a href="/legal/privacy/">Privacy Notice</a>.</label>
    <!-- iamhoiend -->
  </div>

  <div class="subscribe-field subscribe-consent">
    <input type="hidden" name="consent_version" value="2026-08-03">
    <input type="checkbox" id="agit-join-newsletter" name="consent">
    <!-- iamhoi -->
    <label for="agit-join-newsletter">Yes, email me new posts from hoiboy.uk. No spam. You can unsubscribe at any time. See the <a href="/legal/privacy/">Privacy Notice</a>.</label>
    <!-- iamhoiend -->
  </div>

  <div class="subscribe-field cf-turnstile" data-sitekey="0x4AAAAAADz-CB1k9o8zx3S8"></div>

  <div class="subscribe-field">
    <button type="submit">Sign up</button>
  </div>

</form>
</div>

<script src="https://challenges.cloudflare.com/turnstile/v0/api.js" async defer></script>
{{< versioned-script "js/subscribe-form.js" >}}
