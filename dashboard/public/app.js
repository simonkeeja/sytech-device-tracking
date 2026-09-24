/**
 * SYTECH DEVICE TRACKING - Frontend Application Logic (v4.0)
 */

const API_BASE = window.location.origin;
let authToken = localStorage.getItem("sytech_access_token");
let sessionUser = null;
const nativeFetch = window.fetch.bind(window);

window.fetch = (input, init = {}) => {
  const url = typeof input === "string" ? input : input.url;

  if (!authToken || !url.startsWith(API_BASE)) {
    return nativeFetch(input, init);
  }

  const headers = new Headers(init.headers || {});
  headers.set("Authorization", `Bearer ${authToken}`);

  return nativeFetch(input, {
    ...init,
    headers
  });
};

let currentDeviceId = null;
let deviceCache = [];
let previewRequest = 0;
let currentPreview = null;
let currentDevice = null;

let selectedServiceTier = "full_intel_dossier";
let selectedPaymentMethod = "Orange Money";

let ws = null;
let logoTapCount = 0;
let logoTapTimer = null;

// Simulator local states
let phoneFailedAttempts = 0;
let laptopFailedAttempts = 0;


// ============================================================
// INITIALIZATION
// ============================================================

document.addEventListener("DOMContentLoaded", () => {
  document
    .getElementById("loginForm")
    .addEventListener("submit", submitLogin);

  restoreSession();
  setupLogoGesture();
});


// ============================================================
// AUTHENTICATION
// ============================================================

async function restoreSession() {
  if (!authToken) return;

  try {
    const res = await fetch(`${API_BASE}/api/auth/me`);

    if (!res.ok) {
      throw new Error("Session expired");
    }

    sessionUser = await res.json();

    startAuthenticatedDashboard();

  } catch (_) {
    localStorage.removeItem("sytech_access_token");
    authToken = null;
  }
}


async function submitLogin(event) {
  event.preventDefault();

  const error = document.getElementById("loginError");

  try {
    const res = await nativeFetch(
      `${API_BASE}/api/auth/login`,
      {
        method: "POST",

        headers: {
          "Content-Type": "application/json"
        },

        body: JSON.stringify({
          primary_contact:
            document
              .getElementById("loginContact")
              .value
              .trim(),

          password:
            document.getElementById("loginPassword").value
        })
      }
    );

    const data = await res.json();

    if (!res.ok) {
      throw new Error(data.detail || "Sign-in failed");
    }

    authToken = data.access_token;

    localStorage.setItem(
      "sytech_access_token",
      authToken
    );

    sessionUser = data.user;

    startAuthenticatedDashboard();

  } catch (err) {
    error.textContent = err.message;
    error.classList.remove("hidden");
  }
}


async function signOut() {
  try {
    const response = await fetch(
      `${API_BASE}/api/auth/logout`,
      {
        method: "POST"
      }
    );

    if (
      !response.ok &&
      response.status !== 401
    ) {
      throw new Error("Sign-out failed");
    }

    authToken = null;
    sessionUser = null;

    localStorage.removeItem(
      "sytech_access_token"
    );

    if (ws) {
      ws.close();
    }

    window.location.reload();

  } catch (error) {
    notify(
      "Could not sign out. Please retry.",
      "error"
    );
  }
}


function startAuthenticatedDashboard() {
  document.getElementById(
    "backupPinAction"
  ).hidden = false;

  document
    .getElementById("authenticatedWorkspace")
    .classList.remove("hidden");

  document
    .getElementById("signOutBtn")
    .classList.remove("hidden");

  document.getElementById(
    "wsStatus"
  ).textContent =
    sessionUser.role === "customer"
      ? "SIGNED IN"
      : "CONNECTING";

  document
    .getElementById("loginModal")
    .classList.add("hidden");

  document
    .querySelectorAll("[data-roles]")
    .forEach(item => {
      item.classList.toggle(
        "hidden",
        !item.dataset.roles
          .split(",")
          .includes(sessionUser.role)
      );
    });

  if (sessionUser.role !== "customer") {
    initWebSocket();
  }

  loadInitialData();
}


// ============================================================
// NOTIFICATIONS
// ============================================================

function notify(message, tone = "info") {
  const region =
    document.getElementById("toastRegion");

  if (!region) return;

  const toast =
    document.createElement("div");

  toast.className = "toast-message";

  if (tone === "error") {
    toast.style.borderColor = "#be123c";
  }

  if (tone === "success") {
    toast.style.borderColor = "#047857";
  }

  toast.textContent = message;

  region.appendChild(toast);

  window.setTimeout(
    () => toast.remove(),
    5000
  );
}


// ============================================================
// WORKFLOW
// ============================================================

function setWorkflow(
  currentStep,
  summary
) {
  const order = [
    "registered",
    "telemetry",
    "review",
    "complete"
  ];

  const currentIndex =
    order.indexOf(currentStep);

  document.getElementById(
    "workflowSummary"
  ).textContent = summary;

  document
    .querySelectorAll(".workflow-step")
    .forEach(step => {

      const stepIndex =
        order.indexOf(
          step.dataset.step
        );

      step.classList.toggle(
        "is-current",
        stepIndex === currentIndex
      );

      step.classList.toggle(
        "is-complete",
        stepIndex < currentIndex
      );
    });
}


// ============================================================
// CASE HEADER
// ============================================================

function updateCaseHeader(preview) {
  const device =
    currentDevice ||
    preview.device ||
    {};

  const title =
    [
      device.brand,
      device.model
    ]
      .filter(Boolean)
      .join(" ") ||
    "Selected device";

  document.getElementById(
    "selectedDeviceTitle"
  ).textContent =
    device.hardware_identifier
      ? `${title} (${device.hardware_identifier})`
      : title;

  document.getElementById(
    "selectedDeviceOwner"
  ).textContent =
    device.full_name_omang ||
    "Owner details unavailable";

  const badge =
    document.getElementById(
      "caseStatusBadge"
    );

  const lastPing =
    document.getElementById(
      "deviceLastPing"
    );

  if (
    device.current_status === "secured" &&
    preview.status !==
      "no_telemetry_yet"
  ) {
    badge.textContent = "SECURED";

    lastPing.textContent =
      "Reset complete; previous demo events remain in history.";

    setWorkflow(
      "registered",
      "Device secured. Previous demo events and receipts are retained."
    );

  } else if (preview.is_settled) {

    badge.className =
      "px-2.5 py-1 text-xs font-bold rounded-md uppercase tracking-wider bg-emerald-950 text-emerald-300 border border-emerald-800 flex items-center gap-1.5";

    badge.innerHTML =
      '<i class="fa-solid fa-circle-check text-xs"></i> DEMO SETTLED';

    lastPing.textContent =
      "Case evidence is available for download.";

    setWorkflow(
      "complete",
      "Demo settlement complete — the evidence record is available."
    );

  } else if (
    preview.status ===
    "no_telemetry_yet"
  ) {

    badge.className =
      "px-2.5 py-1 text-xs font-bold rounded-md uppercase tracking-wider bg-slate-800 text-slate-300 border border-slate-700 flex items-center gap-1.5";

    badge.innerHTML =
      '<i class="fa-solid fa-clock text-xs"></i> AWAITING TELEMETRY';

    lastPing.textContent =
      "No verified event has been received for this device.";

    setWorkflow(
      "registered",
      "Device is registered — wait for telemetry before taking a recovery action."
    );

  } else {

    badge.className =
      "px-2.5 py-1 text-xs font-bold rounded-md uppercase tracking-wider bg-amber-950 text-amber-300 border border-amber-800 flex items-center gap-1.5";

    badge.innerHTML =
      '<i class="fa-solid fa-shield-halved text-xs"></i> EVIDENCE READY FOR REVIEW';

    lastPing.textContent =
      "Telemetry received — select an appropriate resolution option.";

    setWorkflow(
      "review",
      "Telemetry is ready for review — choose a resolution option when authorized."
    );
  }
}


// ============================================================
// LOGO GESTURE
// ============================================================

function setupLogoGesture() {
  const logo =
    document.getElementById(
      "headerLogo"
    );

  if (!logo) return;

  logo.addEventListener(
    "click",
    () => {
      recordLogoTap();
    }
  );
}


function recordLogoTap() {
  logoTapCount++;

  clearTimeout(
    logoTapTimer
  );

  logoTapTimer =
    setTimeout(() => {
      logoTapCount = 0;
    }, 3000);

  if (logoTapCount >= 5) {
    logoTapCount = 0;
    openMasterPinModal();
  }
}


// ============================================================
// WEBSOCKET
// ============================================================

function initWebSocket() {
  const wsProto =
    window.location.protocol ===
    "https:"
      ? "wss:"
      : "ws:";

  const wsHost =
    window.location.host ||
    "localhost:8000";

  const wsUrl =
    `${wsProto}//${wsHost}/ws/feed`;

  try {
    ws =
      new WebSocket(wsUrl);

    ws.onopen = () => {
      ws.send(authToken);

      const statusEl =
        document.getElementById(
          "wsStatus"
        );

      if (statusEl) {
        statusEl.innerHTML =
          `<i class="fa-solid fa-wifi text-emerald-400"></i><span>SYSTEM LIVE</span>`;
      }
    };

    ws.onmessage = event => {
      try {
        const payload =
          JSON.parse(
            event.data
          );

        handleIncomingWsEvent(
          payload
        );

      } catch (err) {
        console.error(
          "WS Parse error",
          err
        );
      }
    };

    ws.onclose = () => {
      const statusEl =
        document.getElementById(
          "wsStatus"
        );

      if (statusEl) {
        statusEl.innerHTML =
          `<i class="fa-solid fa-wifi text-rose-400"></i><span>RECONNECTING</span>`;
      }

      if (
        authToken &&
        sessionUser &&
        sessionUser.role !==
          "customer"
      ) {
        setTimeout(
          initWebSocket,
          4000
        );
      }
    };

  } catch (err) {
    console.warn(
      "WebSocket connection skipped or not supported:",
      err
    );
  }
}


function handleIncomingWsEvent(
  eventData
) {
  console.log(
    "Incoming Real-time Event:",
    eventData
  );

  if (
    eventData.event ===
    "TELEMETRY_INGRESS"
  ) {

    if (
      eventData.data &&
      Number(
        eventData.data.device_id
      ) ===
        Number(currentDeviceId)
    ) {
      loadDevicePreview(
        currentDeviceId
      );

      loadOperatorCase();
    }

    if (
      sessionUser.role !==
      "customer"
    ) {
      loadTechnicianHubs();
    }

  } else if (
    eventData.event ===
    "FALSE_ALARM_CLEARED"
  ) {

    if (
      eventData.data &&
      Number(
        eventData.data.device_id
      ) ===
        Number(currentDeviceId)
    ) {
      loadDevicePreview(
        currentDeviceId
      );
    }

    resetPhoneSimulator();
    resetLaptopSimulator();

  } else if (
    eventData.event ===
    "INVOICE_SETTLED"
  ) {

    if (
      eventData.data &&
      Number(
        eventData.data.device_id
      ) ===
        Number(currentDeviceId)
    ) {
      loadDevicePreview(
        currentDeviceId
      );
    }
  }
}


// ============================================================
// TAB SWITCHING
// ============================================================

function switchTab(tabId) {
  document
    .querySelectorAll(
      ".tab-content"
    )
    .forEach(el =>
      el.classList.add(
        "hidden"
      )
    );

  document
    .querySelectorAll(
      ".tab-btn"
    )
    .forEach(el =>
      el.classList.remove(
        "active-tab"
      )
    );

  const targetView =
    document.getElementById(
      `view-${tabId}`
    );

  const targetBtn =
    document.getElementById(
      `tab-btn-${tabId}`
    );

  if (targetView) {
    targetView.classList.remove(
      "hidden"
    );
  }

  if (targetBtn) {
    targetBtn.classList.add(
      "active-tab"
    );
  }

  if (
    tabId === "technician"
  ) {
    if (
      sessionUser.role !==
      "customer"
    ) {
      loadTechnicianHubs();
    }
  }

  if (
    tabId === "operator"
  ) {
    loadOperatorCase();
  }
}


// ============================================================
// REGISTERED DEVICE REGISTRY
// ============================================================

function formatDeviceStatus(
  status
) {
  const value =
    String(
      status || "registered"
    ).replaceAll(
      "_",
      " "
    );

  return value.replace(
    /\b\w/g,
    char =>
      char.toUpperCase()
  );
}


function renderDeviceRegistry(
  devices = deviceCache
) {
  const grid =
    document.getElementById(
      "deviceRegistryGrid"
    );

  const empty =
    document.getElementById(
      "deviceRegistryEmpty"
    );

  const summary =
    document.getElementById(
      "deviceRegistrySummary"
    );

  if (
    !grid ||
    !empty ||
    !summary
  ) {
    return;
  }

  grid.innerHTML = "";

  const list =
    Array.isArray(devices)
      ? devices
      : [];

  empty.classList.toggle(
    "hidden",
    list.length > 0
  );

  summary.textContent =
    `${list.length} registered device${list.length === 1 ? "" : "s"} visible to this account.`;

  list.forEach(device => {

    const card =
      document.createElement(
        "button"
      );

    card.type = "button";

    card.dataset.deviceId =
      String(
        device.device_id
      );

    const selected =
      Number(
        device.device_id
      ) ===
      Number(
        currentDeviceId
      );

    card.className =
      `device-registry-card text-left rounded-xl border p-4 transition ${
        selected
          ? "border-cyan-500 bg-cyan-950/20"
          : "border-slate-800 bg-slate-950 hover:border-slate-600 hover:bg-slate-900"
      }`;

    const top =
      document.createElement(
        "div"
      );

    top.className =
      "flex items-start justify-between gap-3";

    const identity =
      document.createElement(
        "div"
      );

    identity.className =
      "min-w-0";

    const name =
      document.createElement(
        "p"
      );

    name.className =
      "font-bold text-white truncate";

    name.textContent =
      [
        device.brand,
        device.model
      ]
        .filter(Boolean)
        .join(" ") ||
      `Device #${device.device_id}`;

    const owner =
      document.createElement(
        "p"
      );

    owner.className =
      "mt-1 text-xs text-slate-400 truncate";

    owner.textContent =
      `Owner: ${
        device.full_name_omang ||
        "Unknown owner"
      }`;

    identity.append(
      name,
      owner
    );

    const badge =
      document.createElement(
        "span"
      );

    badge.className =
      "shrink-0 rounded-md border border-slate-700 bg-slate-900 px-2 py-1 text-[10px] font-bold uppercase text-slate-300";

    badge.textContent =
      formatDeviceStatus(
        device.current_status
      );

    top.append(
      identity,
      badge
    );

    const meta =
      document.createElement(
        "div"
      );

    meta.className =
      "mt-3 space-y-1 text-[11px] text-slate-400";

    const identifier =
      document.createElement(
        "p"
      );

    identifier.className =
      "font-mono break-all text-cyan-300";

    identifier.textContent =
      device.hardware_identifier ||
      "No hardware identifier";

    const type =
      document.createElement(
        "p"
      );

    type.textContent =
      `Type: ${
        device.device_type ||
        "Unknown"
      } • Device ID #${device.device_id}`;

    meta.append(
      identifier,
      type
    );

    card.append(
      top,
      meta
    );

    card.addEventListener(
      "click",
      () =>
        selectRegisteredDevice(
          device.device_id
        )
    );

    grid.appendChild(card);
  });
}


function filterDeviceRegistry(
  query
) {
  const needle =
    String(
      query || ""
    )
      .trim()
      .toLowerCase();

  if (!needle) {
    renderDeviceRegistry(
      deviceCache
    );

    return;
  }

  const filtered =
    deviceCache.filter(
      device =>
        [
          device.device_id,
          device.brand,
          device.model,
          device.hardware_identifier,
          device.device_type,
          device.current_status,
          device.full_name_omang,
          device.owner_primary_contact
        ].some(
          value =>
            String(
              value ?? ""
            )
              .toLowerCase()
              .includes(
                needle
              )
        )
    );

  renderDeviceRegistry(
    filtered
  );
}


async function selectRegisteredDevice(
  deviceId
) {
  currentDeviceId =
    Number(deviceId);

  currentDevice =
    deviceCache.find(
      device =>
        Number(
          device.device_id
        ) ===
        currentDeviceId
    ) || null;

  const selector =
    document.getElementById(
      "deviceSelector"
    );

  if (selector) {
    selector.value =
      String(
        currentDeviceId
      );
  }

  renderDeviceRegistry(
    deviceCache
  );

  await loadDevicePreview(
    currentDeviceId
  );
}


// ============================================================
// INITIAL DEVICE LOADING
// ============================================================

async function loadInitialData() {
  try {
    const res =
      await fetch(
        `${API_BASE}/api/devices`
      );

    if (!res.ok) {
      throw new Error(
        "Could not load devices"
      );
    }

    const devices =
      await res.json();

    deviceCache =
      Array.isArray(devices)
        ? devices
        : [];

    renderDeviceRegistry(
      deviceCache
    );

    document
      .getElementById(
        "emptyDeviceNotice"
      )
      .classList.toggle(
        "hidden",
        deviceCache.length > 0
      );

    const selector =
      document.getElementById(
        "deviceSelector"
      );

    selector.innerHTML = "";

    deviceCache.forEach(
      d => {
        const opt =
          document.createElement(
            "option"
          );

        opt.value =
          d.device_id;

        opt.textContent =
          `${d.brand || ""} ${d.model || ""} (${d.hardware_identifier || "No identifier"})`;

        selector.appendChild(
          opt
        );
      }
    );

    if (
      deviceCache.length > 0
    ) {

      const selected =
        deviceCache.find(
          d =>
            Number(
              d.device_id
            ) ===
            Number(
              currentDeviceId
            )
        ) ||
        deviceCache[0];

      currentDeviceId =
        selected.device_id;

      currentDevice =
        selected;

      selector.value =
        String(
          currentDeviceId
        );

      renderDeviceRegistry(
        deviceCache
      );

      loadDevicePreview(
        currentDeviceId
      );

    } else {

      currentDevice = null;
      currentDeviceId = null;

      document
        .getElementById(
          "caseBody"
        )
        .classList.add(
          "hidden"
        );

      document.getElementById(
        "selectedDeviceTitle"
      ).textContent =
        "No device selected";

      document.getElementById(
        "selectedDeviceOwner"
      ).textContent =
        sessionUser.full_name_omang;

      document.getElementById(
        "caseStatusBadge"
      ).textContent =
        "NO DEVICES";

      document.getElementById(
        "deviceLastPing"
      ).textContent =
        "Register your first device to begin.";

      setWorkflow(
        "registered",
        "No devices are registered yet. Choose Register Device to begin."
      );
    }


    // Populate user select
    const ocrUserSelect =
      document.getElementById(
        "ocrUserIdSelect"
      );

    if (ocrUserSelect) {

      ocrUserSelect.innerHTML =
        "";

      const uniqueUsers = {
        [sessionUser.user_id]:
          sessionUser.full_name_omang
      };

      const ownOption =
        document.createElement(
          "option"
        );

      ownOption.value =
        sessionUser.user_id;

      ownOption.textContent =
        `${sessionUser.full_name_omang} (Your account)`;

      ocrUserSelect.appendChild(
        ownOption
      );

      deviceCache.forEach(
        d => {

          if (
            d.user_id &&
            !uniqueUsers[
              d.user_id
            ]
          ) {

            const ownerName =
              d.full_name_omang ||
              `User ID #${d.user_id}`;

            uniqueUsers[
              d.user_id
            ] = ownerName;

            const uOpt =
              document.createElement(
                "option"
              );

            uOpt.value =
              d.user_id;

            uOpt.textContent =
              `${ownerName} (User ID #${d.user_id})`;

            ocrUserSelect.appendChild(
              uOpt
            );
          }
        }
      );
    }


    if (
      sessionUser.role !==
      "customer"
    ) {
      loadTechnicianHubs();
    }

  } catch (err) {

    console.error(
      "Failed to load initial data",
      err
    );

    setWorkflow(
      "registered",
      "The device list could not be loaded. Check the server connection and try again."
    );

    notify(
      "Could not load the device list.",
      "error"
    );
  }
}


function refreshCurrentDevice() {
  if (currentDeviceId) {
    loadDevicePreview(
      currentDeviceId
    );
  }
}


// ============================================================
// DEVICE PREVIEW
// ============================================================

async function loadDevicePreview(
  deviceId
) {
  if (!deviceId) return;

  const request =
    ++previewRequest;

  currentDeviceId =
    parseInt(deviceId);

  currentDevice =
    deviceCache.find(
      device =>
        Number(
          device.device_id
        ) ===
        Number(
          currentDeviceId
        )
    ) || null;

  renderDeviceRegistry(
    deviceCache
  );

  const caseBody =
    document.getElementById(
      "caseBody"
    );

  caseBody.classList.add(
    "hidden"
  );

  const selector =
    document.getElementById(
      "deviceSelector"
    );

  if (selector) {
    selector.value =
      String(
        currentDeviceId
      );
  }

  try {

    const res =
      await fetch(
        `${API_BASE}/api/devices/${currentDeviceId}/preview`
      );

    if (!res.ok) {

      let message =
        "Could not load device preview";

      try {
        const errorData =
          await res.json();

        message =
          errorData.detail ||
          message;

      } catch (_) {
        // Ignore JSON parsing failure
      }

      throw new Error(
        message
      );
    }

    const data =
      await res.json();

    if (
      request !==
      previewRequest
    ) {
      return;
    }

    if (data.device) {
      currentDevice = {
        ...currentDevice,
        ...data.device
      };
    }

    currentPreview = data;

    updateCaseHeader(data);

    renderDeviceRegistry(
      deviceCache
    );


    const baseFee =
      Number(
        (
          currentDevice &&
          currentDevice.success_fee_calculated
        ) || 0
      );

    const registrationFee =
      (
        currentDevice &&
        currentDevice.is_registration_paid
      )
        ? 0
        : 50;


    document.getElementById(
      "receiptStore"
    ).textContent =
      "Unverified";

    document.getElementById(
      "receiptPrice"
    ).textContent =
      `BWP ${Number(
        (
          currentDevice &&
          currentDevice.purchase_price_bwp
        ) || 0
      ).toFixed(2)}`;

    document.getElementById(
      "regFeeStatus"
    ).textContent =
      registrationFee
        ? "P50.00 deferred"
        : "Demo registration settled";

    document.getElementById(
      "optionATotalDisplay"
    ).textContent =
      `BWP ${(baseFee + registrationFee).toFixed(2)}`;

    document.getElementById(
      "optionABaseFee"
    ).textContent =
      `P${baseFee.toFixed(2)}`;

    document.getElementById(
      "optionADeferredFee"
    ).textContent =
      `P${registrationFee.toFixed(2)}`;

    document.getElementById(
      "optionBTotalDisplay"
    ).textContent =
      `BWP ${(50 + registrationFee).toFixed(2)}`;

    document.getElementById(
      "optionBDeferredFee"
    ).textContent =
      `P${registrationFee.toFixed(2)}`;


    const photoEl =
      document.getElementById(
        "suspectPhotoImg"
      );

    const photoOverlay =
      document.getElementById(
        "photoLockOverlay"
      );

    const nameEl =
      document.getElementById(
        "suspectNameText"
      );

    const phoneEl =
      document.getElementById(
        "suspectPhoneText"
      );

    const carrierEl =
      document.getElementById(
        "suspectCarrierText"
      );

    const imsiEl =
      document.getElementById(
        "suspectImsiText"
      );

    const bssidEl =
      document.getElementById(
        "suspectBssidText"
      );

    const badgeEl =
      document.getElementById(
        "settlementBadge"
      );

    const unlockedBanner =
      document.getElementById(
        "unlockedDossierBanner"
      );

    const downloadBtn =
      document.getElementById(
        "downloadAffidavitBtn"
      );

    const socialContainer =
      document.getElementById(
        "socialLinksContainer"
      );


    photoEl.removeAttribute(
      "src"
    );

    imsiEl.textContent =
      "Unavailable before demo settlement";

    bssidEl.textContent =
      "Unavailable before demo settlement";

    socialContainer.textContent =
      "Simulated links unavailable before demo settlement";

    downloadBtn.onclick = null;

    downloadBtn.removeAttribute(
      "href"
    );

    document.getElementById(
      "faceMatchConfidence"
    ).textContent =
      "No verified face match";


    // ========================================================
    // SETTLED
    // ========================================================

    if (data.is_settled) {

      badgeEl.innerHTML =
        `<span class="px-3 py-1 rounded-full text-xs font-semibold bg-emerald-950 text-emerald-300 border border-emerald-800 flex items-center gap-1.5">
          <i class="fa-solid fa-unlock"></i>
          SIMULATED RESULTS UNLOCKED
        </span>`;

      photoEl.classList.remove(
        "blur-md"
      );

      photoEl.src =
        data.photo_url || "";

      photoOverlay.classList.add(
        "hidden"
      );

      nameEl.textContent =
        data.suspect_name ||
        "No suspect identity";

      nameEl.classList.remove(
        "text-amber-400"
      );

      nameEl.classList.add(
        "text-emerald-400"
      );

      phoneEl.textContent =
        data.phone_number ||
        "Not provided";

      carrierEl.textContent =
        data.carrier
          ? `(${data.carrier})`
          : "";

      imsiEl.textContent =
        data.imsi ||
        "Not provided";

      bssidEl.textContent =
        data.wifi_bssid ||
        "Not provided";


      socialContainer.innerHTML =
        "";

      (
        data.social_links ||
        []
      ).forEach(link => {

        if (
          !/^https?:\/\//i.test(
            link
          )
        ) {
          return;
        }

        const item =
          document.createElement(
            "a"
          );

        item.href = link;
        item.target = "_blank";

        item.rel =
          "noopener noreferrer";

        item.className =
          "px-3 py-1.5 rounded-lg bg-slate-800 text-xs text-cyan-300 hover:text-white border border-cyan-800 flex items-center gap-2 transition";

        item.textContent =
          link;

        socialContainer.appendChild(
          item
        );
      });


      unlockedBanner.classList.remove(
        "hidden"
      );

      downloadBtn.href = "#";

      downloadBtn.onclick =
        async event => {

          event.preventDefault();

          try {

            const response =
              await fetch(
                `${API_BASE}/api/devices/${currentDeviceId}/affidavit-pdf`
              );

            if (!response.ok) {
              throw new Error(
                "Download failed. Check your session and dossier entitlement."
              );
            }

            const url =
              URL.createObjectURL(
                await response.blob()
              );

            const anchor =
              document.createElement(
                "a"
              );

            anchor.href = url;

            anchor.download =
              `SYTECH_DEMO_REPORT_${currentDeviceId}.pdf`;

            anchor.click();

            setTimeout(
              () =>
                URL.revokeObjectURL(
                  url
                ),
              1000
            );

          } catch (error) {

            notify(
              error.message,
              "error"
            );
          }
        };


      const checkout =
        document.getElementById(
          "checkoutSubmitBtn"
        );

      checkout.disabled = true;

      checkout.innerHTML =
        `<i class="fa-solid fa-circle-check text-emerald-400"></i> Dossier Settled & Unlocked`;

      checkout.classList.replace(
        "from-cyan-600",
        "from-slate-700"
      );

      checkout.classList.replace(
        "to-blue-600",
        "to-slate-800"
      );


    // ========================================================
    // NO TELEMETRY
    // ========================================================

    } else if (
      data.status ===
      "no_telemetry_yet"
    ) {

      badgeEl.innerHTML =
        `<span class="px-3 py-1 rounded-full text-xs font-semibold bg-slate-800 text-slate-300 border border-slate-700 flex items-center gap-1.5">
          <i class="fa-solid fa-clock"></i>
          Awaiting telemetry
        </span>`;

      photoEl.classList.add(
        "blur-md"
      );

      photoOverlay.classList.remove(
        "hidden"
      );

      nameEl.textContent =
        "No evidence captured";

      nameEl.classList.remove(
        "text-emerald-400"
      );

      nameEl.classList.add(
        "text-slate-300"
      );

      phoneEl.textContent = "—";

      carrierEl.textContent = "";

      imsiEl.textContent =
        "No SIM telemetry received";

      bssidEl.textContent =
        "No nearby-network telemetry received";

      socialContainer.innerHTML =
        `<span class="text-xs text-slate-500">
          Evidence fields remain unavailable until a telemetry event arrives.
        </span>`;

      unlockedBanner.classList.add(
        "hidden"
      );

      const checkout =
        document.getElementById(
          "checkoutSubmitBtn"
        );

      checkout.disabled = true;

      checkout.innerHTML =
        `<i class="fa-solid fa-lock text-slate-400"></i> Await telemetry`;

      checkout.classList.replace(
        "from-cyan-600",
        "from-slate-700"
      );

      checkout.classList.replace(
        "to-blue-600",
        "to-slate-800"
      );


    // ========================================================
    // PAYWALL
    // ========================================================

    } else {

      badgeEl.innerHTML =
        `<span class="px-3 py-1 rounded-full text-xs font-semibold bg-amber-950 text-amber-300 border border-amber-800 flex items-center gap-1.5">
          <i class="fa-solid fa-lock"></i>
          Evidence Obscured (Pending Settlement)
        </span>`;

      photoEl.classList.add(
        "blur-md"
      );

      photoOverlay.classList.remove(
        "hidden"
      );

      nameEl.textContent =
        data.suspect_name_masked ||
        "Th*** M*****";

      nameEl.classList.add(
        "text-amber-400"
      );

      nameEl.classList.remove(
        "text-emerald-400"
      );

      phoneEl.textContent =
        data.phone_number_masked ||
        "+267 71 **** 67";

      carrierEl.textContent =
        `(${data.carrier || "Orange Botswana"})`;

      unlockedBanner.classList.add(
        "hidden"
      );


      if (data.pricing) {

        const optA =
          data.pricing.option_a_dossier;

        const optB =
          data.pricing.option_b_data_recovery;

        document.getElementById(
          "receiptPrice"
        ).textContent =
          `BWP ${data.pricing.verified_purchase_price.toLocaleString(
            "en-US",
            {
              minimumFractionDigits: 2
            }
          )}`;

        document.getElementById(
          "regFeeStatus"
        ).textContent =
          data.pricing.deferred_reg_fee > 0
            ? "P50.00 (Deferred - Pay Once)"
            : "P0.00 (Paid)";

        document.getElementById(
          "optionATotalDisplay"
        ).textContent =
          `BWP ${optA.total_due.toFixed(2)}`;

        document.getElementById(
          "optionABaseFee"
        ).textContent =
          `P${optA.base_fee.toFixed(2)}`;

        document.getElementById(
          "optionADeferredFee"
        ).textContent =
          `P${optA.deferred_reg_fee.toFixed(2)}`;

        document.getElementById(
          "optionBTotalDisplay"
        ).textContent =
          `BWP ${optB.total_due.toFixed(2)}`;

        document.getElementById(
          "optionBDeferredFee"
        ).textContent =
          `P${optB.deferred_reg_fee.toFixed(2)}`;

        updateCheckoutButtonLabel();
      }


      const checkout =
        document.getElementById(
          "checkoutSubmitBtn"
        );

      checkout.disabled = false;

      checkout.classList.replace(
        "from-slate-700",
        "from-cyan-600"
      );

      checkout.classList.replace(
        "to-slate-800",
        "to-blue-600"
      );
    }


    caseBody.classList.remove(
      "hidden"
    );


  // ==========================================================
  // PREVIEW FALLBACK
  // ==========================================================

  } catch (err) {

    console.error(
      "Failed to load device preview",
      err
    );

    try {

      const detailRes =
        await fetch(
          `${API_BASE}/api/devices/${currentDeviceId}`
        );

      if (detailRes.ok) {

        const detail =
          await detailRes.json();

        if (detail.device) {

          currentDevice = {
            ...currentDevice,
            ...detail.device
          };
        }

        if (detail.user) {

          currentDevice =
            currentDevice || {};

          currentDevice.full_name_omang =
            detail.user.full_name_omang;

          currentDevice.owner_primary_contact =
            detail.user.primary_contact;
        }
      }

    } catch (detailErr) {

      console.warn(
        "Device detail fallback also failed",
        detailErr
      );
    }


    const fallbackDevice =
      currentDevice || {};

    const title =
      [
        fallbackDevice.brand,
        fallbackDevice.model
      ]
        .filter(Boolean)
        .join(" ") ||
      `Device #${currentDeviceId}`;


    document.getElementById(
      "selectedDeviceTitle"
    ).textContent =
      fallbackDevice.hardware_identifier
        ? `${title} (${fallbackDevice.hardware_identifier})`
        : title;


    document.getElementById(
      "selectedDeviceOwner"
    ).textContent =
      fallbackDevice.full_name_omang ||
      "Owner details unavailable";


    const badge =
      document.getElementById(
        "caseStatusBadge"
      );

    badge.className =
      "px-2.5 py-1 text-xs font-bold rounded-md uppercase tracking-wider bg-slate-800 text-slate-300 border border-slate-700 flex items-center gap-1.5";

    badge.textContent =
      formatDeviceStatus(
        fallbackDevice.current_status ||
        "registered"
      );


    document.getElementById(
      "deviceLastPing"
    ).textContent =
      "Registered device loaded; case preview is currently unavailable.";


    caseBody.classList.add(
      "hidden"
    );


    setWorkflow(
      "registered",
      "Registered device loaded. Case preview data could not be loaded."
    );


    renderDeviceRegistry(
      deviceCache
    );


    notify(
      "Device is registered, but its case preview could not be loaded.",
      "error"
    );
  }
}


// ============================================================
// PRICING
// ============================================================

function selectPricingOption(
  tier
) {
  selectedServiceTier =
    tier;

  const cardA =
    document.getElementById(
      "card-option-a"
    );

  const cardB =
    document.getElementById(
      "card-option-b"
    );

  if (
    tier ===
    "full_intel_dossier"
  ) {

    cardA.classList.add(
      "active-pricing-card",
      "border-cyan-500"
    );

    cardA.classList.remove(
      "border-slate-700"
    );

    cardB.classList.remove(
      "active-pricing-card",
      "border-purple-500"
    );

    cardB.classList.add(
      "border-slate-700"
    );

  } else {

    cardB.classList.add(
      "active-pricing-card",
      "border-purple-500"
    );

    cardB.classList.remove(
      "border-slate-700"
    );

    cardA.classList.remove(
      "active-pricing-card",
      "border-cyan-500"
    );

    cardA.classList.add(
      "border-slate-700"
    );
  }

  updateCheckoutButtonLabel();
}


function updateCheckoutButtonLabel() {
  const button =
    document.getElementById(
      "checkoutSubmitBtn"
    );

  if (
    !currentPreview ||
    currentPreview.status ===
      "no_telemetry_yet"
  ) {
    button.textContent =
      "Await telemetry";

    return;
  }

  if (
    currentPreview.is_settled
  ) {
    button.textContent =
      "Demo dossier settled";

    return;
  }

  const fullDossier =
    selectedServiceTier ===
    "full_intel_dossier";

  const total =
    document.getElementById(
      fullDossier
        ? "optionATotalDisplay"
        : "optionBTotalDisplay"
    ).textContent;

  button.textContent =
    `${fullDossier ? "Unlock demo dossier" : "Simulate recovery fee"} - ${total}`;
}


function selectPaymentMethod(
  method
) {
  selectedPaymentMethod =
    method;

  document
    .querySelectorAll(
      ".pay-method-btn"
    )
    .forEach(
      b =>
        b.classList.remove(
          "active-method"
        )
    );

  if (
    method ===
    "Orange Money"
  ) {
    document
      .getElementById(
        "btn-pay-orange"
      )
      .classList.add(
        "active-method"
      );
  }

  if (
    method ===
    "MyZaka"
  ) {
    document
      .getElementById(
        "btn-pay-myzaka"
      )
      .classList.add(
        "active-method"
      );
  }

  if (
    method ===
    "Smega"
  ) {
    document
      .getElementById(
        "btn-pay-smega"
      )
      .classList.add(
        "active-method"
      );
  }
}


// ============================================================
// DEMO CONFIRMATION
// ============================================================

function confirmDemoAction(
  message
) {
  const dialog =
    document.getElementById(
      "demoConfirmDialog"
    );

  if (dialog.open) {
    return Promise.resolve(
      false
    );
  }

  document.getElementById(
    "demoConfirmMessage"
  ).textContent =
    message;

  dialog.returnValue =
    "cancel";

  return new Promise(
    resolve => {

      dialog.addEventListener(
        "close",
        () =>
          resolve(
            dialog.returnValue ===
              "confirm"
          ),
        {
          once: true
        }
      );

      dialog.showModal();
    }
  );
}


// ============================================================
// CHECKOUT
// ============================================================

async function executePaymentCheckout() {
  const submitBtn =
    document.getElementById(
      "checkoutSubmitBtn"
    );

  if (
    submitBtn.disabled ||
    !currentDeviceId
  ) {
    return;
  }

  const checkout = {
    device_id:
      currentDeviceId,

    selected_service:
      selectedServiceTier,

    payment_method:
      selectedPaymentMethod
  };


  if (
    !await confirmDemoAction(
      `Confirm the demo settlement for Device #${currentDeviceId} using ${selectedPaymentMethod}? No money will be transferred.`
    )
  ) {
    return;
  }


  submitBtn.disabled =
    true;

  const storageKey =
    `sytech_checkout_${sessionUser.user_id}_${JSON.stringify(checkout)}`;

  submitBtn.innerHTML =
    `<i class="fa-solid fa-spinner fa-spin"></i> Processing ${selectedPaymentMethod} Payment...`;


  try {

    const retryKey =
      localStorage.getItem(
        storageKey
      ) ||
      crypto.randomUUID();

    localStorage.setItem(
      storageKey,
      retryKey
    );


    const res =
      await fetch(
        `${API_BASE}/api/invoices/checkout`,
        {
          method: "POST",

          headers: {
            "Content-Type":
              "application/json"
          },

          body:
            JSON.stringify({
              ...checkout,
              idempotency_key:
                retryKey
            })
        }
      );


    const result =
      await res.json();


    if (res.ok) {

      notify(
        `Demo settlement complete: ${result.invoice.gateway_reference} • BWP ${result.invoice.total_due.toFixed(2)}`,
        "success"
      );

      loadDevicePreview(
        currentDeviceId
      );

    } else {

      notify(
        `Settlement failed: ${result.detail || "Unknown error"}`,
        "error"
      );
    }

  } catch (err) {

    notify(
      "Could not connect to the checkout service.",
      "error"
    );

  } finally {

    submitBtn.disabled =
      false;
  }
}


// ============================================================
// HTML ESCAPE
// ============================================================

function escapeHtml(value) {
  const element =
    document.createElement(
      "span"
    );

  element.textContent =
    String(
      value == null
        ? ""
        : value
    );

  return element.innerHTML;
}


// ============================================================
// OPERATOR TELEMETRY
// ============================================================

function appendTelemetryRow(
  data
) {
  data = {
    ...data,
    device_id:
      Number(
        data.device_id
      )
  };

  for (
    const field of [
      "trigger_type",
      "captured_network_operator",
      "new_sim_number_imsi",
      "captured_ip"
    ]
  ) {
    data[field] =
      escapeHtml(
        data[field]
      );
  }


  data.enrichment =
    Object.fromEntries(
      Object.entries(
        data.enrichment ||
        {}
      ).map(
        ([key, value]) => [
          key,
          escapeHtml(value)
        ]
      )
    );


  const tbody =
    document.getElementById(
      "telemetryLogTable"
    );

  if (!tbody) return;


  const tr =
    document.createElement(
      "tr"
    );

  tr.className =
    "hover:bg-slate-800/60 transition";


  const now =
    data.logged_at
      ? new Date(
          data.logged_at
        ).toLocaleString()
      : new Date()
          .toLocaleTimeString();


  tr.innerHTML = `
    <td class="p-3 font-mono text-slate-400">
      ${escapeHtml(now)}
    </td>

    <td class="p-3 font-bold text-white">
      Device #${data.device_id}
    </td>

    <td class="p-3">
      <span class="px-2 py-0.5 rounded text-[10px] font-bold bg-rose-950 text-rose-400 border border-rose-800">
        ${data.trigger_type || "Unknown"}
      </span>
    </td>

    <td class="p-3 font-mono text-cyan-300">
      ${data.new_sim_number_imsi || "No SIM data"}
    </td>

    <td class="p-3 font-mono text-slate-400">
      ${data.captured_network_operator || "Not captured"}
      <br/>
      ${data.captured_ip || "Not captured"}
    </td>

    <td class="p-3">
      <span class="px-2 py-0.5 rounded text-[10px] font-bold bg-emerald-950 text-emerald-400 border border-emerald-800">
        READY
      </span>
    </td>

    <td class="p-3">
      <button
        onclick="selectRegisteredDevice(${data.device_id}); switchTab('paywall');"
        class="px-2 py-1 bg-cyan-700 hover:bg-cyan-600 text-white rounded text-[10px]"
      >
        View Case
      </button>
    </td>
  `;


  tbody.insertBefore(
    tr,
    tbody.firstChild
  );
}


async function loadOperatorCase() {
  const tbody =
    document.getElementById(
      "telemetryLogTable"
    );

  if (
    !tbody ||
    !currentDeviceId
  ) {
    return;
  }


  tbody.innerHTML =
    `<tr>
      <td colspan="7" class="p-6 text-center text-xs text-slate-500">
        <i class="fa-solid fa-spinner fa-spin mr-2"></i>
        Loading selected case history…
      </td>
    </tr>`;


  try {

    const res =
      await fetch(
        `${API_BASE}/api/devices/${currentDeviceId}`
      );


    if (!res.ok) {

      let message =
        "Could not load case history";

      try {
        const errorData =
          await res.json();

        message =
          errorData.detail ||
          message;

      } catch (_) {}

      throw new Error(
        message
      );
    }


    const data =
      await res.json();


    if (data.device) {

      currentDevice = {
        ...currentDevice,
        ...data.device
      };
    }


    if (
      data.user &&
      currentDevice
    ) {

      currentDevice.full_name_omang =
        data.user.full_name_omang;

      currentDevice.owner_primary_contact =
        data.user.primary_contact;
    }


    const intelLogs =
      data.intel_logs ||
      [];


    tbody.innerHTML = "";


    if (
      !intelLogs.length
    ) {

      tbody.innerHTML =
        `<tr>
          <td colspan="7" class="p-6 text-center text-xs text-slate-500">
            No telemetry has been recorded for this device.
          </td>
        </tr>`;

      return;
    }


    intelLogs
      .slice()
      .reverse()
      .forEach(
        log =>
          appendTelemetryRow({
            ...log,

            device_id:
              currentDeviceId,

            enrichment: {
              carrier:
                log.captured_network_operator
            }
          })
      );


  } catch (err) {

    console.error(
      "Failed to load operator case",
      err
    );

    tbody.innerHTML =
      `<tr>
        <td colspan="7" class="p-6 text-center text-xs text-rose-400">
          Case history could not be loaded.
        </td>
      </tr>`;
  }
}


// ============================================================
// TECHNICIAN HUBS
// ============================================================

async function loadTechnicianHubs() {
  try {

    const res =
      await fetch(
        `${API_BASE}/api/technician-hubs`
      );

    if (!res.ok) {
      throw new Error(
        "Could not load technician hubs"
      );
    }

    const data =
      await res.json();

    const container =
      document.getElementById(
        "technicianHubsList"
      );

    if (!container) return;

    container.innerHTML = "";


    if (
      !data.hubs ||
      data.hubs.length === 0
    ) {

      container.innerHTML = `
        <div class="col-span-2 bg-slate-950 p-6 rounded-xl border border-slate-800 text-center">
          <i class="fa-solid fa-shield-check text-emerald-400 text-2xl mb-2"></i>

          <p class="text-xs text-slate-400">
            No multi-device BSSID clusters currently detected in Gaborone shopping districts.
          </p>
        </div>
      `;

      return;
    }


    data.hubs.forEach(
      hub => {

        const card =
          document.createElement(
            "div"
          );

        card.className =
          "bg-slate-950 border border-rose-900/60 p-4 rounded-xl shadow-lg space-y-3";


        let devicesHtml =
          "";

        (
          hub.compromised_devices ||
          []
        ).forEach(
          d => {

            devicesHtml +=
              `<li class="text-[11px] text-slate-300">
                • <b>Device #${escapeHtml(d.device_id)}</b>:
                ${escapeHtml(d.model)}
                (${escapeHtml(d.imei_or_serial)})
              </li>`;
          }
        );


        card.innerHTML = `
          <div class="flex items-start justify-between">

            <div>

              <span class="px-2 py-0.5 rounded text-[10px] font-bold bg-rose-950 text-rose-400 border border-rose-800 uppercase">
                ${escapeHtml(hub.threat_level)}
              </span>

              <h4 class="text-sm font-bold text-white mt-1.5">
                ${escapeHtml(hub.location_zone)}
              </h4>

              <p class="text-[11px] font-mono text-cyan-400">
                Hardware BSSID:
                ${escapeHtml(hub.bssid)}
              </p>

            </div>

            <span class="text-xs font-bold text-rose-400 bg-rose-950/80 px-2 py-1 rounded border border-rose-800">
              ${escapeHtml(hub.distinct_devices_count)}
              Devices Detected
            </span>

          </div>

          <div class="bg-slate-900/80 p-2.5 rounded-lg border border-slate-800">

            <span class="text-[10px] uppercase font-mono text-slate-400 block mb-1">
              Trapped Hardware Inventory:
            </span>

            <ul class="space-y-1">
              ${devicesHtml}
            </ul>

          </div>

          <p class="text-[10px] text-amber-400 italic">
            <i class="fa-solid fa-bullhorn mr-1"></i>
            ${escapeHtml(hub.recommended_action)}
          </p>
        `;


        container.appendChild(
          card
        );
      }
    );


  } catch (err) {

    console.error(
      "Failed to load technician hubs",
      err
    );
  }
}


// ============================================================
// DEVICE REGISTRATION
// ============================================================

async function submitNewDeviceWithReceipt() {

  const userId =
    document.getElementById(
      "ocrUserIdSelect"
    ).value ||
    sessionUser.user_id;

  const brand =
    document.getElementById(
      "regBrand"
    ).value.trim();

  const model =
    document.getElementById(
      "regModel"
    ).value.trim();

  const hwId =
    document.getElementById(
      "regHwId"
    ).value.trim();

  const storeName =
    document.getElementById(
      "regStoreName"
    ).value;

  const priceBwp =
    parseFloat(
      document.getElementById(
        "regPriceBwp"
      ).value
    );

  const backupPin =
    document.getElementById(
      "regBackupPin"
    ).value;


  const resultBox =
    document.getElementById(
      "ocrResultBox"
    );


  if (
    !brand ||
    !model ||
    !hwId ||
    !Number.isFinite(priceBwp) ||
    priceBwp <= 0
  ) {

    resultBox.innerHTML =
      `<p class="text-rose-400">
        Complete the brand, model, hardware identifier and purchase price.
      </p>`;

    return;
  }


  if (
    !/^\d{6,12}$/.test(
      backupPin
    )
  ) {

    resultBox.innerHTML =
      `<p class="text-rose-400">
        Backup PIN must contain 6–12 digits.
      </p>`;

    return;
  }


  resultBox.innerHTML =
    `<p class="text-purple-400">
      <i class="fa-solid fa-spinner fa-spin mr-1"></i>
      Registering device; receipt remains unverified...
    </p>`;


  try {

    const res =
      await fetch(
        `${API_BASE}/api/devices/register`,
        {
          method: "POST",

          headers: {
            "Content-Type":
              "application/json"
          },

          body:
            JSON.stringify({
              user_id:
                parseInt(userId),

              device_type:
                "smartphone",

              brand:
                brand,

              model:
                model,

              hardware_identifier:
                hwId,

              purchase_price_bwp:
                priceBwp,

              store_name:
                storeName,

              master_backup_pin:
                backupPin
            })
        }
      );


    const data =
      await res.json();


    if (res.ok) {

      currentDeviceId =
        data.device_id;

      const ocr =
        data.ocr_verification ||
        {};

      const fee =
        Number(
          ocr.calculated_success_fee_bwp ||
          0
        );


      resultBox.textContent =
        `Device #${data.device_id} registered. Receipt and identity unverified. Estimated fee: P${fee.toFixed(2)}.`;


      await loadInitialData();

      switchTab(
        "paywall"
      );


    } else {

      resultBox.textContent =
        "Registration failed: " +
        (
          typeof data.detail ===
          "string"
            ? data.detail
            : JSON.stringify(
                data.detail
              )
        );
    }


  } catch (err) {

    console.error(
      "Device registration failed",
      err
    );

    resultBox.innerHTML =
      `<p class="text-rose-400">
        Network error during device registration.
      </p>`;
  }
}


// ============================================================
// MASTER BACKUP PIN
// ============================================================

function openMasterPinModal() {

  if (!currentDeviceId) {

    notify(
      "Select a device first.",
      "error"
    );

    return;
  }

  document
    .getElementById(
      "masterPinModal"
    )
    .classList.remove(
      "hidden"
    );

  document.getElementById(
    "masterPinInput"
  ).value = "";

  document.getElementById(
    "masterPinInput"
  ).focus();
}


function closeMasterPinModal() {

  document
    .getElementById(
      "masterPinModal"
    )
    .classList.add(
      "hidden"
    );
}


async function submitMasterPin() {

  const pin =
    document.getElementById(
      "masterPinInput"
    ).value;


  try {

    const res =
      await fetch(
        `${API_BASE}/api/devices/${currentDeviceId}/verify-master-pin`,
        {
          method: "POST",

          headers: {
            "Content-Type":
              "application/json"
          },

          body:
            JSON.stringify({
              device_id:
                currentDeviceId,

              entered_pin:
                pin
            })
        }
      );


    const data =
      await res.json();


    if (res.ok) {

      notify(
        "Reset successful: device secured.",
        "success"
      );

      closeMasterPinModal();

      loadDevicePreview(
        currentDeviceId
      );

      resetPhoneSimulator();
      resetLaptopSimulator();

    } else {

      notify(
        "Access denied: " +
        (
          data.detail ||
          "Incorrect PIN"
        ),
        "error"
      );
    }


  } catch (err) {

    notify(
      "Connection error verifying PIN.",
      "error"
    );
  }
}


// ============================================================
// REMOTE TOKEN
// ============================================================

async function generateRemoteTokenForCurrentDevice() {

  if (!currentDeviceId) {

    notify(
      "Select a device first.",
      "error"
    );

    return;
  }


  const verified =
    document.getElementById(
      "operatorIdentityVerified"
    );


  if (
    !verified ||
    !verified.checked
  ) {

    notify(
      "Confirm caller verification before generating a reset token.",
      "error"
    );

    return;
  }


  if (
    !await confirmDemoAction(
      `Generate a single-use reset token for Device #${currentDeviceId}?`
    )
  ) {
    return;
  }


  try {

    const res =
      await fetch(
        `${API_BASE}/api/devices/${currentDeviceId}/generate-remote-token`,
        {
          method: "POST"
        }
      );


    const data =
      await res.json();


    if (res.ok) {

      document.getElementById(
        "remoteTokenDisplay"
      ).value =
        data.remote_token;

      notify(
        `Single-use reset token generated for Device #${currentDeviceId}.`,
        "success"
      );

    } else {

      notify(
        data.detail ||
        "Could not generate reset token.",
        "error"
      );
    }


  } catch (err) {

    notify(
      "Could not generate a reset token.",
      "error"
    );
  }
}


// ============================================================
// SAMPLE DEMO TELEMETRY
// ============================================================

async function triggerSampleStolenEvent() {

  if (!currentDeviceId) {

    notify(
      "Select a device first.",
      "error"
    );

    return;
  }


  try {

    const response =
      await fetch(
        `${API_BASE}/api/telemetry/ingress`,
        {
          method: "POST",

          headers: {
            "Content-Type":
              "application/json"
          },

          body:
            JSON.stringify({
              device_id:
                currentDeviceId,

              trigger_type:
                "sim_swap",

              local_failed_attempts:
                3,

              new_sim_number_imsi:
                "652028912384910",

              new_phone_number:
                "+26771234567",

              captured_network_operator:
                "Orange Botswana",

              nearby_wifi_macs:
                "A4:2B:B0:19:C2:5E,88:DE:A9:31:8B:20"
            })
        }
      );


    if (!response.ok) {

      let message =
        "Demo telemetry is unavailable.";

      try {

        const data =
          await response.json();

        message =
          data.detail ||
          message;

      } catch (_) {}

      notify(
        message,
        "error"
      );

      return;
    }


    notify(
      "Demo telemetry event submitted.",
      "success"
    );


  } catch (err) {

    console.error(err);

    notify(
      "Could not submit demo telemetry.",
      "error"
    );
  }
}


// ============================================================
// TRAPPHON SIMULATOR
// ============================================================

function simulatePhoneUnlockAttempt() {

  if (!currentDeviceId) {

    notify(
      "Select a device first.",
      "error"
    );

    return;
  }


  phoneFailedAttempts++;


  document.getElementById(
    "phoneFailedAttemptsText"
  ).textContent =
    `Failed attempts: ${phoneFailedAttempts} / 3`;


  if (
    phoneFailedAttempts >= 3
  ) {

    document
      .getElementById(
        "phoneNormalState"
      )
      .classList.add(
        "hidden"
      );

    document
      .getElementById(
        "phoneHoneypotState"
      )
      .classList.remove(
        "hidden"
      );


    fetch(
      `${API_BASE}/api/telemetry/ingress`,
      {
        method: "POST",

        headers: {
          "Content-Type":
            "application/json"
        },

        body:
          JSON.stringify({
            device_id:
              currentDeviceId,

            trigger_type:
              "failed_login",

            local_failed_attempts:
              phoneFailedAttempts
          })
      }
    ).catch(
      err =>
        console.error(
          err
        )
    );
  }
}


function simulateSimInsertion() {

  if (!currentDeviceId) {

    notify(
      "Select a device first.",
      "error"
    );

    return;
  }


  alert(
    "Demo SIM insertion event.\nA simulated telemetry event will be sent to the SYTECH backend."
  );


  fetch(
    `${API_BASE}/api/telemetry/ingress`,
    {
      method: "POST",

      headers: {
        "Content-Type":
          "application/json"
      },

      body:
        JSON.stringify({
          device_id:
            currentDeviceId,

          trigger_type:
            "sim_swap",

          new_sim_number_imsi:
            "652028912384910",

          new_phone_number:
            "+26771234567",

          captured_network_operator:
            "Orange Botswana"
        })
    }
  ).catch(
    err =>
      console.error(
        err
      )
  );
}


function resetPhoneSimulator() {

  phoneFailedAttempts = 0;

  const normal =
    document.getElementById(
      "phoneNormalState"
    );

  const honeypot =
    document.getElementById(
      "phoneHoneypotState"
    );

  const attempts =
    document.getElementById(
      "phoneFailedAttemptsText"
    );

  const input =
    document.getElementById(
      "simPhonePinInput"
    );


  if (normal) {
    normal.classList.remove(
      "hidden"
    );
  }

  if (honeypot) {
    honeypot.classList.add(
      "hidden"
    );
  }

  if (attempts) {
    attempts.textContent =
      "Failed attempts: 0 / 3";
  }

  if (input) {
    input.value = "";
  }
}


// ============================================================
// TRAPLAP SIMULATOR
// ============================================================

function simulateLaptopUnlockAttempt() {

  laptopFailedAttempts++;


  document.getElementById(
    "laptopAttemptsText"
  ).textContent =
    `Failed logins: ${laptopFailedAttempts} / 3`;


  if (
    laptopFailedAttempts >= 3
  ) {

    document
      .getElementById(
        "laptopNormalState"
      )
      .classList.add(
        "hidden"
      );

    document
      .getElementById(
        "laptopCaptiveState"
      )
      .classList.remove(
        "hidden"
      );
  }
}


function triggerLaptopBiosAttempt() {

  alert(
    "Demo boot-attempt event detected.\nThe simulator will display the captive lockout state."
  );

  document
    .getElementById(
      "laptopNormalState"
    )
    .classList.add(
      "hidden"
    );

  document
    .getElementById(
      "laptopCaptiveState"
    )
    .classList.remove(
      "hidden"
    );
}


function triggerLaptopWebcamFlash() {

  const led =
    document.getElementById(
      "laptopWebcamLed"
    );

  if (!led) return;


  led.classList.replace(
    "bg-cyan-400",
    "bg-rose-500"
  );


  setTimeout(
    () => {

      led.classList.replace(
        "bg-rose-500",
        "bg-cyan-400"
      );

      alert(
        "Demo camera indicator activated. No real image capture occurs in this browser simulation."
      );

    },
    300
  );
}


function simulateLaptopWifiConnect() {

  if (!currentDeviceId) {

    notify(
      "Select a device first.",
      "error"
    );

    return;
  }


  alert(
    "Demo Wi-Fi connection event.\nSimulated network telemetry will be sent to the SYTECH backend."
  );


  fetch(
    `${API_BASE}/api/telemetry/ingress`,
    {
      method: "POST",

      headers: {
        "Content-Type":
          "application/json"
      },

      body:
        JSON.stringify({
          device_id:
            currentDeviceId,

          trigger_type:
            "wifi_captive_connect",

          nearby_wifi_macs:
            "A4:2B:B0:19:C2:5E,B2:11:C4:58:AA:12",

          captured_ip:
            "168.167.12.84",

          captured_network_operator:
            "Botswana Telecom (BTC Fiber)"
        })
    }
  ).catch(
    err =>
      console.error(
        err
      )
  );
}


function resetLaptopSimulator() {

  laptopFailedAttempts = 0;


  const normal =
    document.getElementById(
      "laptopNormalState"
    );

  const captive =
    document.getElementById(
      "laptopCaptiveState"
    );

  const attempts =
    document.getElementById(
      "laptopAttemptsText"
    );

  const input =
    document.getElementById(
      "laptopPassInput"
    );


  if (normal) {
    normal.classList.remove(
      "hidden"
    );
  }

  if (captive) {
    captive.classList.add(
      "hidden"
    );
  }

  if (attempts) {
    attempts.textContent =
      "Failed logins: 0 / 3";
  }

  if (input) {
    input.value = "";
  }
}


// ============================================================
// CHANGE BACKUP PIN
// ============================================================

async function changeBackupPin(
  event
) {

  event.preventDefault();


  if (!currentDeviceId) {

    return notify(
      "Select a device first.",
      "error"
    );
  }


  const form =
    event.target;

  const button =
    form.querySelector(
      "button"
    );

  button.disabled =
    true;


  try {

    const response =
      await fetch(
        `${API_BASE}/api/devices/${currentDeviceId}/backup-pin`,
        {
          method: "PUT",

          headers: {
            "Content-Type":
              "application/json"
          },

          body:
            JSON.stringify({
              password:
                document.getElementById(
                  "pinAccountPassword"
                ).value,

              new_pin:
                document.getElementById(
                  "replacementPin"
                ).value
            })
        }
      );


    const data =
      await response.json();


    if (!response.ok) {

      throw new Error(
        typeof data.detail ===
        "string"
          ? data.detail
          : "Please check the password and PIN."
      );
    }


    form.reset();


    notify(
      "Backup PIN saved. Use it above to reset the demo device.",
      "success"
    );


  } catch (error) {

    notify(
      error.message,
      "error"
    );

  } finally {

    button.disabled =
      false;
  }
}