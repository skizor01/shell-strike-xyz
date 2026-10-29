import { createClient } from "https://esm.sh/@supabase/supabase-js@2";
import { SUPABASE_URL, SUPABASE_ANON_KEY } from "../assets/supabase-config.js";

const supabase = createClient(SUPABASE_URL, SUPABASE_ANON_KEY, {
  auth: { persistSession: true, autoRefreshToken: true, detectSessionInUrl: true }
});
const $ = (selector) => document.querySelector(selector);
let currentUser = null;
let settings = null;
let applications = [];
const OWNER_USER_ID = "7dadb17c-ed5c-4198-b5a2-b6783d20404c";
const isOwner = () => currentUser?.id === OWNER_USER_ID;

function setStatus(selector, message, isError = false) {
  const el = $(selector);
  el.textContent = message;
  el.classList.toggle("error", isError);
}
function escapeHtml(value = "") {
  return String(value).replace(/[&<>"']/g, (ch) => ({
    "&":"&amp;", "<":"&lt;", ">":"&gt;", '"':"&quot;", "'":"&#39;"
  })[ch]);
}

async function isAdmin() {
  const { data, error } = await supabase.rpc("is_shell_strike_admin");
  if (error) throw error;
  return data === true;
}
async function loadSettings() {
  const { data, error } = await supabase.from("site_settings")
    .select("id,is_accepting_applications,applications_closed_message,application_limit,updated_at")
    .eq("id", true).single();
  if (error) throw error;
  settings = data;
  $("#applicationToggle").classList.toggle("on", data.is_accepting_applications);
  $("#applicationToggle").setAttribute("aria-pressed", String(data.is_accepting_applications));
  $("#statusPill").textContent = data.is_accepting_applications ? "Applications open" : "Applications closed";
  $("#statusPill").className = "pill " + (data.is_accepting_applications ? "open" : "closed");
  $("#closedMessage").value = data.applications_closed_message || "";
  $("#applicationLimit").value = data.application_limit == null ? "unlimited" : String(data.application_limit);
}
function renderApplications() {
  const filter = $("#statusFilter").value;
  const visible = filter === "all" ? applications : applications.filter((a) => a.status === filter);
  $("#totalCount").textContent = applications.length;
  $("#pendingCount").textContent = applications.filter((a) => a.status === "pending").length;
  $("#reviewedCount").textContent = applications.filter((a) => a.status !== "pending").length;
  const root = $("#applicationsList");
  if (!visible.length) {
    root.innerHTML = '<p class="empty">No applications in this view.</p>';
    return;
  }
  root.innerHTML = visible.map((a) => `
    <article class="application" data-id="${escapeHtml(a.id)}">
      <div class="app-top">
        <div><h3>${escapeHtml(a.in_game_name)} · ${escapeHtml(a.desired_role)}</h3>
        <div class="meta">Discord: ${escapeHtml(a.discord_handle)} · Submitted ${new Date(a.created_at).toLocaleString()}</div></div>
        <span class="pill ${a.status === "accepted" ? "open" : a.status === "rejected" ? "closed" : ""}">${escapeHtml(a.status)}</span>
      </div>
      <p><strong>Experience</strong><br>${escapeHtml(a.experience)}</p>
      <p><strong>Why they want to join</strong><br>${escapeHtml(a.motivation)}</p>
      <div class="app-controls">
        <select class="review-status" aria-label="Application status">
          <option value="pending" ${a.status === "pending" ? "selected" : ""}>Pending</option>
          <option value="accepted" ${a.status === "accepted" ? "selected" : ""}>Accepted</option>
          <option value="rejected" ${a.status === "rejected" ? "selected" : ""}>Rejected</option>
        </select>
        <textarea class="review-notes" maxlength="2000" placeholder="Private reviewer notes">${escapeHtml(a.reviewer_notes || "")}</textarea>
      </div>
      <div class="actions"><button class="btn small-btn save-review">Save review</button></div>
    </article>
  `).join("");
  root.querySelectorAll(".save-review").forEach((button) => button.addEventListener("click", async () => {
    const article = button.closest(".application");
    const id = article.dataset.id;
    const status = article.querySelector(".review-status").value;
    const reviewer_notes = article.querySelector(".review-notes").value.trim();
    button.disabled = true;
    button.textContent = "Saving…";
    const { error } = await supabase.from("staff_applications").update({
      status, reviewer_notes, reviewed_by: currentUser.id, reviewed_at: new Date().toISOString()
    }).eq("id", id);
    button.disabled = false;
    button.textContent = "Save review";
    if (error) {
      setStatus("#settingsStatus", "Couldn't save this review. Check your connection and permissions.", true);
      return;
    }
    setStatus("#settingsStatus", "Application review saved.");
    await loadApplications();
  }));
}
async function loadApplications() {
  const { data, error } = await supabase.from("staff_applications")
    .select("id,in_game_name,discord_handle,desired_role,experience,motivation,status,reviewer_notes,created_at")
    .order("created_at", { ascending: false }).limit(500);
  if (error) throw error;
  applications = data || [];
  renderApplications();
}
async function loadAdminUsers() {
  const root = $("#adminUsersList");
  const status = $("#adminAccessStatus");
  root.innerHTML = '<p class="empty">Loading authorized admins…</p>';
  status.textContent = "";
  const { data, error } = await supabase.from("admin_users")
    .select("user_id,created_at")
    .order("created_at", { ascending: true });
  if (error) {
    root.innerHTML = '<p class="empty">Could not load the admin list.</p>';
    setStatus("#adminAccessStatus", "Admin list failed to load. Check the admin_users SELECT grant and RLS policy.", true);
    return;
  }
  const admins = data || [];
  if (!admins.length) {
    root.innerHTML = '<p class="empty">No authorized admins found.</p>';
    return;
  }
  root.innerHTML = admins.map((admin) => {
    const owner = admin.user_id === OWNER_USER_ID;
    const self = admin.user_id === currentUser?.id;
    const canRevoke = isOwner() && !owner;
    return `
      <article class="admin-row">
        <div>
          <div><strong>${owner ? "Shell Strike Owner" : "Authorized Admin"}${self ? " (you)" : ""}</strong></div>
          <div class="admin-id">${escapeHtml(admin.user_id)}</div>
          <div class="admin-date">Added ${admin.created_at ? new Date(admin.created_at).toLocaleString() : "date unavailable"}</div>
        </div>
        <div>${canRevoke ? `<button class="btn small-btn danger-btn revoke-admin" data-user-id="${escapeHtml(admin.user_id)}">Revoke access</button>` : `<span class="pill">${owner ? "Owner" : "Admin"}</span>`}</div>
      </article>`;
  }).join("");
  root.querySelectorAll(".revoke-admin").forEach((button) => button.addEventListener("click", async () => {
    const targetUserId = button.dataset.userId;
    if (!isOwner() || targetUserId === OWNER_USER_ID) {
      setStatus("#adminAccessStatus", "You are not permitted to revoke this account.", true);
      return;
    }
    if (!window.confirm(`Revoke admin access for ${targetUserId}? This takes effect immediately.`)) return;
    button.disabled = true;
    button.textContent = "Revoking…";
    const { error: revokeError } = await supabase.rpc("revoke_shell_strike_admin", {
      p_target_user_id: targetUserId
    });
    if (revokeError) {
      button.disabled = false;
      button.textContent = "Revoke access";
      setStatus("#adminAccessStatus", revokeError.message || "Could not revoke access.", true);
      return;
    }
    setStatus("#adminAccessStatus", "Admin access revoked.");
    await loadAdminUsers();
  }));
}
async function loadDashboard() {
  await loadSettings();
  await loadAdminUsers();
  await loadApplications();
}
async function routeAuth() {
  const { data: { user }, error } = await supabase.auth.getUser();
  if (error) console.warn("Auth check:", error.message);
  currentUser = user;
  $("#loginPanel").classList.add("hidden");
  $("#deniedPanel").classList.add("hidden");
  $("#dashboard").classList.add("hidden");
  $("#signOutButton").classList.add("hidden");
  $("#userLabel").textContent = "";
  const avatar = $("#userAvatar");
  avatar.removeAttribute("src");
  avatar.classList.remove("visible");
  avatar.onerror = () => { avatar.removeAttribute("src"); avatar.classList.remove("visible"); };
  if (!user) {
    $("#loginPanel").classList.remove("hidden");
    return;
  }
  const metadata = user.user_metadata || {};
  $("#userLabel").textContent = metadata.full_name || metadata.name || metadata.global_name || metadata.preferred_username || user.email || "Signed in";
  const discordAvatar = metadata.avatar_url || metadata.picture || metadata.avatarUrl || metadata.photo_url;
  if (discordAvatar && typeof discordAvatar === "string") {
    avatar.src = discordAvatar;
    avatar.classList.add("visible");
  } else if (metadata.avatar && (metadata.provider_id || metadata.sub)) {
    const discordId = metadata.provider_id || metadata.sub;
    avatar.src = `https://cdn.discordapp.com/avatars/${encodeURIComponent(discordId)}/${encodeURIComponent(metadata.avatar)}.png?size=96`;
    avatar.classList.add("visible");
  }
  $("#signOutButton").classList.remove("hidden");
  let allowed = false;
  try { allowed = await isAdmin(); } catch (err) { console.error(err); }
  if (!allowed) {
    $("#deniedPanel").classList.remove("hidden");
    return;
  }
  $("#dashboard").classList.remove("hidden");
  try { await loadDashboard(); }
  catch (err) {
    console.error(err);
    setStatus("#settingsStatus", "Could not load admin data. Verify that schema.sql was run and this account is allowlisted.", true);
  }
}
async function signOut() {
  await supabase.auth.signOut();
  currentUser = null;
  await routeAuth();
}

$("#signInButton").addEventListener("click", async () => {
  setStatus("#loginStatus", "Redirecting to Discord…");
  const { error } = await supabase.auth.signInWithOAuth({
    provider: "discord",
    options: { redirectTo: `${window.location.origin}/admin/`, scopes: "identify" }
  });
  if (error) setStatus("#loginStatus", "Discord sign-in could not start. Check the Supabase provider configuration.", true);
});
$("#signOutButton").addEventListener("click", signOut);
$("#deniedSignOut").addEventListener("click", signOut);
$("#applicationToggle").addEventListener("click", () => {
  if (!settings) return;
  settings.is_accepting_applications = !settings.is_accepting_applications;
  $("#applicationToggle").classList.toggle("on", settings.is_accepting_applications);
  $("#applicationToggle").setAttribute("aria-pressed", String(settings.is_accepting_applications));
  $("#statusPill").textContent = settings.is_accepting_applications ? "Applications open (unsaved)" : "Applications closed (unsaved)";
});
$("#saveSettings").addEventListener("click", async () => {
  if (!settings) return;
  const message = $("#closedMessage").value.trim();
  if (!message || message.length > 500) {
    setStatus("#settingsStatus", "Enter a closed message of 1–500 characters.", true);
    return;
  }
  const limitValue = $("#applicationLimit").value;
  const application_limit = limitValue === "unlimited" ? null : Number(limitValue);
  const saveButton = $("#saveSettings");
  saveButton.disabled = true;
  saveButton.textContent = "Saving…";
  const { error } = await supabase.from("site_settings").update({
    is_accepting_applications: settings.is_accepting_applications,
    applications_closed_message: message,
    application_limit,
    updated_at: new Date().toISOString()
  }).eq("id", true);
  saveButton.disabled = false;
  saveButton.textContent = "Save settings";
  if (error) {
    setStatus("#settingsStatus", "Settings were not saved. Check your admin authorization and database setup.", true);
    return;
  }
  setStatus("#settingsStatus", "Settings saved securely.");
  await loadSettings();
});
$("#refreshButton").addEventListener("click", async () => {
  try { await loadDashboard(); setStatus("#settingsStatus", "Data refreshed."); }
  catch (err) { setStatus("#settingsStatus", "Refresh failed. Check your connection.", true); }
});
$("#statusFilter").addEventListener("change", renderApplications);
$("#refreshAdminsButton").addEventListener("click", loadAdminUsers);

supabase.auth.onAuthStateChange(() => {
  // Defer the async check so Supabase can finish updating its internal session state.
  setTimeout(() => routeAuth(), 0);
});
routeAuth();
