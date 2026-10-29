import { createClient } from "https://esm.sh/@supabase/supabase-js@2";
import { SUPABASE_URL, SUPABASE_ANON_KEY } from "../assets/supabase-config.js";

const supabase = createClient(SUPABASE_URL, SUPABASE_ANON_KEY);
const form = document.querySelector("#applicationForm");
const closedNotice = document.querySelector("#closedNotice");
const closedMessage = document.querySelector("#closedMessage");
const formStatus = document.querySelector("#formStatus");
const loadStatus = document.querySelector("#loadStatus");
const submitButton = document.querySelector("#submitButton");

function showError(message) {
  formStatus.textContent = message;
  formStatus.classList.add("error");
}

async function loadSettings() {
  if (SUPABASE_URL.includes("YOUR-PROJECT-REF") || SUPABASE_ANON_KEY.includes("YOUR-SUPABASE")) {
    loadStatus.textContent = "Site setup is incomplete. Please try again later.";
    return;
  }
  const { data, error } = await supabase.from("site_settings")
    .select("is_accepting_applications, applications_closed_message, application_limit")
    .eq("id", true).single();
  loadStatus.hidden = true;
  if (error || !data) {
    closedNotice.hidden = false;
    closedMessage.textContent = "Applications are temporarily unavailable. Please check back later.";
    return;
  }
  if (data.is_accepting_applications) {
    form.hidden = false;
    form.dataset.limitReached = data.application_limit !== null && Number(data.application_limit) <= 0 ? "true" : "false";
  } else {
    closedNotice.hidden = false;
    closedMessage.textContent = data.applications_closed_message || "Staff applications are currently closed. Check back later for updates.";
  }
}

form.addEventListener("submit", async (event) => {
  event.preventDefault();
  formStatus.textContent = "";
  formStatus.classList.remove("error");
  if (document.querySelector("#website").value.trim()) return; // basic honeypot
  submitButton.disabled = true;
  submitButton.textContent = "Submitting…";
  const values = {
    p_in_game_name: document.querySelector("#ign").value.trim(),
    p_discord_handle: document.querySelector("#discord").value.trim(),
    p_desired_role: document.querySelector("#role").value,
    p_experience: document.querySelector("#experience").value.trim(),
    p_motivation: document.querySelector("#motivation").value.trim()
  };
  const { error } = await supabase.rpc("submit_staff_application", values);
  submitButton.disabled = false;
  submitButton.textContent = "Submit application ↗";
  if (error) {
    const msg = error.message || "";
    if (msg.includes("APPLICATIONS_CLOSED")) {
      form.hidden = true;
      closedNotice.hidden = false;
      closedMessage.textContent = "Staff applications are currently closed. Check back later for updates.";
      return;
    }
    if (msg.includes("APPLICATION_LIMIT_REACHED")) {
      form.hidden = true;
      closedNotice.hidden = false;
      closedMessage.textContent = "The application limit has been reached. Check back later for updates.";
      return;
    }
    showError(msg.includes("Failed to fetch") ? "Could not connect. Please try again." : "We couldn't submit your application. Check your answers and try again.");
    return;
  }
  form.reset();
  formStatus.classList.remove("error");
  formStatus.textContent = "Application submitted. Thanks for your interest in Shell Strike.";
  submitButton.textContent = "Application submitted";
  submitButton.disabled = true;
});

loadSettings();
