const apiUrl = "/validate_batch";

// Main Element Bindings
const smilesInput = document.getElementById("smilesInput");
const csvInput = document.getElementById("csvInput");
const runBtn = document.getElementById("runBtn");
const clearBtn = document.getElementById("clearBtn");
const statusEl = document.getElementById("status");
const resultsBody = document.getElementById("resultsBody");
const passRateEl = document.getElementById("passRate");
const countEl = document.getElementById("count");
const runsBody = document.getElementById("runsBody");
const refreshRuns = document.getElementById("refreshRuns");
const selectedRun = document.getElementById("selectedRun");
const downloadPdf = document.getElementById("downloadPdf");

// Chatbot Element Bindings
const toggleSettings = document.getElementById("toggleSettings");
const apiKeyPanel = document.getElementById("apiKeyPanel");
const apiKeyInput = document.getElementById("apiKeyInput");
const saveApiKey = document.getElementById("saveApiKey");
const chatMessages = document.getElementById("chatMessages");
const chatInput = document.getElementById("chatInput");
const sendChatBtn = document.getElementById("sendChatBtn");

// Details Modal Element Bindings
const detailsModal = document.getElementById("detailsModal");
const closeModalBtn = document.getElementById("closeModalBtn");
const modalStructureImage = document.getElementById("modalStructureImage");
const modalSmiles = document.getElementById("modalSmiles");
const modalMolWt = document.getElementById("modalMolWt");
const modalHeavyAtoms = document.getElementById("modalHeavyAtoms");
const modalRings = document.getElementById("modalRings");
const modalEnergy = document.getElementById("modalEnergy");
const checkZ3 = document.getElementById("checkZ3");
const checkRDKit = document.getElementById("checkRDKit");
const checkStability = document.getElementById("checkStability");
const toggleRawJson = document.getElementById("toggleRawJson");
const rawJsonArea = document.getElementById("rawJsonArea");

// Auth Bindings
const showAuthModalBtn = document.getElementById("showAuthModalBtn");
const logoutBtn = document.getElementById("logoutBtn");
const userInfoContainer = document.getElementById("userInfoContainer");
const userWelcomeText = document.getElementById("userWelcomeText");

const authModal = document.getElementById("authModal");
const closeAuthModalBtn = document.getElementById("closeAuthModalBtn");
const tabLogin = document.getElementById("tabLogin");
const tabRegister = document.getElementById("tabRegister");
const authForm = document.getElementById("authForm");
const authUsername = document.getElementById("authUsername");
const authPassword = document.getElementById("authPassword");
const authErrorMsg = document.getElementById("authErrorMsg");
const authSubmitBtn = document.getElementById("authSubmitBtn");

// Global state variables
let lastResults = [];
let verdictChartInstance = null;
let energyChartInstance = null;
let activeUser = sessionStorage.getItem("active_user") || null;
let authMode = "login";

// Helpers
const setStatus = (text, tone = "info") => {
  statusEl.textContent = text;
  statusEl.className = tone === "error" ? "text-sm text-rose-400 mt-2 font-medium" : "text-sm text-indigo-400 mt-2 font-medium";
};

// Auth Actions & UI controller
const updateAuthStateUI = () => {
  if (activeUser) {
    showAuthModalBtn.classList.add("hidden");
    userInfoContainer.classList.remove("hidden");
    userInfoContainer.classList.add("flex");
    userWelcomeText.textContent = `Logged in: ${activeUser}`;
  } else {
    showAuthModalBtn.classList.remove("hidden");
    userInfoContainer.classList.add("hidden");
    userInfoContainer.classList.remove("flex");
    userWelcomeText.textContent = "";
  }
  loadRuns();
};

const selectAuthTab = (mode) => {
  authMode = mode;
  if (mode === "login") {
    tabLogin.className = "flex-1 pb-2.5 text-sm font-bold text-indigo-400 border-b-2 border-indigo-500 focus:outline-none";
    tabRegister.className = "flex-1 pb-2.5 text-sm font-bold text-slate-500 border-b-2 border-transparent focus:outline-none";
    authSubmitBtn.textContent = "Login";
  } else {
    tabRegister.className = "flex-1 pb-2.5 text-sm font-bold text-indigo-400 border-b-2 border-indigo-500 focus:outline-none";
    tabLogin.className = "flex-1 pb-2.5 text-sm font-bold text-slate-500 border-b-2 border-transparent focus:outline-none";
    authSubmitBtn.textContent = "Sign Up";
  }
};

// API Key Storage / Config
if (sessionStorage.getItem("openai_api_key")) {
  apiKeyInput.value = sessionStorage.getItem("openai_api_key");
}

toggleSettings.addEventListener("click", () => {
  apiKeyPanel.classList.toggle("hidden");
});

saveApiKey.addEventListener("click", () => {
  const key = apiKeyInput.value.trim();
  if (key) {
    sessionStorage.setItem("openai_api_key", key);
    alert("API Key saved securely for this session!");
  } else {
    sessionStorage.removeItem("openai_api_key");
    alert("API Key cleared.");
  }
  apiKeyPanel.classList.add("hidden");
});

// CSV Parser
const parseCsvFirstColumn = async (file) => {
  const text = await file.text();
  const lines = text.split(/\r?\n/).filter((line) => line.trim().length > 0);
  if (lines.length === 0) {
    return [];
  }

  const values = lines.map((line) => line.split(",")[0].trim());
  const cleaned = values.filter((value) => value.length > 0);
  if (cleaned.length && cleaned[0].toLowerCase().includes("smiles")) {
    return cleaned.slice(1);
  }
  return cleaned;
};

// Render Visual Charts
const updateCharts = (results) => {
  const visualsPanel = document.getElementById("visualsPanel");
  if (!results || !results.length) {
    visualsPanel.classList.add("hidden");
    return;
  }
  visualsPanel.classList.remove("hidden");

  if (verdictChartInstance) verdictChartInstance.destroy();
  if (energyChartInstance) energyChartInstance.destroy();

  const passCount = results.filter(r => r.verdict === "PASS").length;
  const failCount = results.filter(r => r.verdict === "FAIL").length;
  const unknownCount = results.filter(r => r.verdict !== "PASS" && r.verdict !== "FAIL").length;

  const ctxVerdict = document.getElementById("verdictChart").getContext("2d");
  verdictChartInstance = new Chart(ctxVerdict, {
    type: 'doughnut',
    data: {
      labels: ['PASS', 'FAIL', 'UNKNOWN'],
      datasets: [{
        data: [passCount, failCount, unknownCount],
        backgroundColor: ['rgba(16, 185, 129, 0.75)', 'rgba(244, 63, 94, 0.75)', 'rgba(245, 158, 11, 0.75)'],
        borderColor: ['#10b981', '#f43f5e', '#f59e0b'],
        borderWidth: 1
      }]
    },
    options: {
      responsive: true,
      plugins: {
        legend: {
          position: 'bottom',
          labels: { color: '#94a3b8', font: { size: 10 } }
        }
      }
    }
  });

  const scatterData = results.map(r => {
    return {
      x: r.metadata?.mol_wt || 0,
      y: r.energy_kcal_mol || 0,
      label: r.smiles || "",
      verdict: r.verdict
    };
  });

  const ctxEnergy = document.getElementById("energyChart").getContext("2d");
  energyChartInstance = new Chart(ctxEnergy, {
    type: 'scatter',
    data: {
      datasets: [
        {
          label: 'PASS',
          data: scatterData.filter(d => d.verdict === 'PASS'),
          backgroundColor: '#10b981',
          pointRadius: 6
        },
        {
          label: 'FAIL/UNKNOWN',
          data: scatterData.filter(d => d.verdict !== 'PASS'),
          backgroundColor: '#f43f5e',
          pointRadius: 6
        }
      ]
    },
    options: {
      responsive: true,
      maintainAspectRatio: false,
      scales: {
        x: {
          title: { display: true, text: 'Molecular Weight (g/mol)', color: '#94a3b8' },
          ticks: { color: '#94a3b8' },
          grid: { color: 'rgba(255,255,255,0.05)' }
        },
        y: {
          title: { display: true, text: 'Energy (kcal/mol)', color: '#94a3b8' },
          ticks: { color: '#94a3b8' },
          grid: { color: 'rgba(255,255,255,0.05)' }
        }
      },
      plugins: {
        tooltip: {
          callbacks: {
            label: function(context) {
              const item = context.raw;
              return `${item.label} (MW: ${item.x.toFixed(1)}, Energy: ${item.y.toFixed(1)})`;
            }
          }
        },
        legend: {
          labels: { color: '#94a3b8' }
        }
      }
    }
  });
};

// Details Modal Handlers
const openDetailsModal = (row) => {
  if (row.structure_png) {
    modalStructureImage.innerHTML = `<img src="data:image/png;base64,${row.structure_png}" class="max-h-[180px] w-full object-contain" alt="structure" />`;
  } else {
    modalStructureImage.innerHTML = `<span class="text-xs text-slate-500 font-medium">No structure rendering available</span>`;
  }

  modalSmiles.textContent = row.smiles || "—";
  modalMolWt.textContent = row.metadata?.mol_wt ? `${row.metadata.mol_wt.toFixed(2)} g/mol` : "—";
  modalHeavyAtoms.textContent = row.metadata?.heavy_atoms ?? "—";
  modalRings.textContent = row.metadata?.rings ?? "—";
  modalEnergy.textContent = row.energy_kcal_mol ? `${row.energy_kcal_mol.toFixed(2)} kcal/mol` : "—";

  const updateIcon = (el, isPass) => {
    el.className = isPass
      ? "fa-solid fa-circle-check text-emerald-400 mr-2 text-base"
      : "fa-solid fa-circle-xmark text-rose-500 mr-2 text-base";
  };
  
  updateIcon(checkZ3, row.z3_pass);
  updateIcon(checkRDKit, row.rdkit_pass);
  
  const isStable = row.stable === true || (row.stable === null && row.energy_kcal_mol !== null && row.energy_kcal_mol < 50.0);
  updateIcon(checkStability, isStable);

  rawJsonArea.textContent = JSON.stringify(row, null, 2);
  rawJsonArea.classList.add("hidden");

  detailsModal.classList.remove("hidden");
};

closeModalBtn.addEventListener("click", () => {
  detailsModal.classList.add("hidden");
});

toggleRawJson.addEventListener("click", () => {
  rawJsonArea.classList.toggle("hidden");
});

// Render results inside HTML Table
const renderResults = (results) => {
  resultsBody.innerHTML = "";
  lastResults = results;
  if (!results.length) {
    passRateEl.textContent = "—";
    countEl.textContent = "0";
    resultsBody.innerHTML = `<tr><td colspan="6" class="px-4 py-8 text-center text-slate-500 text-xs">No validation results inside this run.</td></tr>`;
    updateCharts([]);
    return;
  }

  const passCount = results.filter((row) => row.verdict === "PASS").length;
  const passRate = ((passCount / results.length) * 100).toFixed(1);
  passRateEl.textContent = `${passRate}%`;
  countEl.textContent = `${results.length}`;

  results.forEach((row) => {
    const tr = document.createElement("tr");
    tr.className = "result-row divide-x divide-slate-900 border-b border-slate-900";
    
    const structureCell = row.structure_png
      ? `<img src="data:image/png;base64,${row.structure_png}" class="h-10 w-16 rounded-md bg-slate-950/40 object-contain mx-auto" alt="structure" />`
      : `<span class="text-xs text-slate-500">—</span>`;

    const reasons = (row.reasons && row.reasons.length ? row.reasons : row.violations || []).join("; ");

    tr.innerHTML = `
      <td class="px-4 py-2.5 text-center">${structureCell}</td>
      <td class="px-4 py-2.5 text-xs text-slate-300 font-mono select-all truncate max-w-[150px]">${row.smiles || "—"}</td>
      <td class="px-4 py-2.5 text-center">
        <span class="rounded-full px-2.5 py-0.5 text-xxs font-bold ${row.verdict === "PASS" ? "bg-emerald-500/20 text-emerald-300 border border-emerald-500/30" : row.verdict === "UNKNOWN" ? "bg-amber-500/20 text-amber-300 border border-amber-500/30" : "bg-rose-500/20 text-rose-300 border border-rose-500/30"}">
          ${row.verdict}
        </span>
      </td>
      <td class="px-4 py-2.5 text-xs text-slate-200 text-center font-semibold">${row.energy_kcal_mol !== null ? row.energy_kcal_mol.toFixed(2) : "—"}</td>
      <td class="px-4 py-2.5 text-xs text-slate-400 text-center">${row.classical_method ?? row.method ?? "—"}</td>
      <td class="px-4 py-2.5 text-xs text-slate-400 truncate max-w-[200px]">${reasons || "—"}</td>
    `;
    
    tr.addEventListener("click", () => openDetailsModal(row));
    resultsBody.appendChild(tr);
  });

  updateCharts(results);
};

// PDF Exporter
const exportPdf = () => {
  if (!lastResults.length) {
    setStatus("No results to export.", "error");
    return;
  }

  const { jsPDF } = window.jspdf;
  const doc = new jsPDF({ orientation: "portrait", unit: "mm", format: "a4" });

  const pageWidth = doc.internal.pageSize.getWidth();
  const pageHeight = doc.internal.pageSize.getHeight();
  const leftMargin = 15;
  const rightMargin = 15;
  const topMargin = 12;
  const bottomMargin = 15;
  const tableTop = 45;
  const lineHeight = 4.5;
  const headerHeight = 8;
  const tableWidth = pageWidth - leftMargin - rightMargin;

  const colWidths = [22, 50, 18, 28, 24, 38];
  const cols = ["Structure", "SMILES", "Verdict", "Energy (kcal/mol)", "Method", "Reason"];

  const parseRgb = (rgbString) => {
    if (!rgbString) return [255, 255, 255];
    const m = rgbString.match(/rgba?\(([^)]+)\)/);
    if (!m) return [255, 255, 255];
    const parts = m[1].split(/,/).map((p) => p.trim());
    return [parseInt(parts[0], 10) || 255, parseInt(parts[1], 10) || 255, parseInt(parts[2], 10) || 255];
  };

  const bodyBg = window.getComputedStyle(document.body).backgroundColor;
  const [pageBgR, pageBgG, pageBgB] = parseRgb(bodyBg);

  const drawPageHeader = () => {
    doc.setFillColor(pageBgR, pageBgG, pageBgB);
    doc.rect(0, 0, pageWidth, pageHeight, "F");

    doc.setFont("helvetica", "bold");
    doc.setFontSize(16);
    doc.setTextColor(255 - Math.round(pageBgR * 0.8), 255 - Math.round(pageBgG * 0.8), 255 - Math.round(pageBgB * 0.8));
    doc.text("Q-NEXUS Validation Results", pageWidth / 2, topMargin + 6, { align: "center" });

    const now = new Date();
    doc.setFont("helvetica", "normal");
    doc.setFontSize(9);
    doc.setTextColor(180, 180, 180);
    doc.text(`Date: ${now.toLocaleDateString()}`, leftMargin, topMargin + 14);
    doc.text(`Time: ${now.toLocaleTimeString([], { hour: "numeric", minute: "2-digit", second: "2-digit" })}`, leftMargin, topMargin + 20);
    doc.setTextColor(0, 0, 0);
  };

  const drawTableHeader = (y) => {
    doc.setFont("helvetica", "bold");
    doc.setFontSize(9);

    let x = leftMargin;
    cols.forEach((col, i) => {
      doc.text(col, x + 1, y + 5);
      x += colWidths[i];
    });

    doc.setLineWidth(0.2);
    doc.line(leftMargin, y, leftMargin + tableWidth, y);
    doc.line(leftMargin, y + headerHeight, leftMargin + tableWidth, y + headerHeight);

    x = leftMargin;
    doc.line(x, y, x, y + headerHeight);
    colWidths.forEach((width) => {
      x += width;
      doc.line(x, y, x, y + headerHeight);
    });
  };

  const wrapText = (value, width) => doc.splitTextToSize(String(value ?? "—"), Math.max(width - 2, 10));

  const drawRow = (y, rowData) => {
    doc.setFont("helvetica", "normal");
    doc.setFontSize(8);

    const wrappedSmiles = wrapText(rowData.smiles, colWidths[1]);
    const wrappedVerdict = wrapText(rowData.verdict, colWidths[2]);
    const wrappedEnergy = wrapText(rowData.energy, colWidths[3]);
    const wrappedMethod = wrapText(rowData.method, colWidths[4]);
    const wrappedReason = wrapText(rowData.reason, colWidths[5]);

    const textMaxLines = Math.max(
      wrappedSmiles.length,
      wrappedVerdict.length,
      wrappedEnergy.length,
      wrappedMethod.length,
      wrappedReason.length,
      1
    );

    const imageHeight = rowData.structurePng ? 12 : 0;
    const rowHeight = Math.max(textMaxLines * lineHeight + 2, imageHeight + 4);

    let x = leftMargin;
    if (rowData.structurePng) {
      const imageData = `data:image/png;base64,${rowData.structurePng}`;
      try {
        doc.addImage(imageData, "PNG", x + 2, y + 2, 16, 12);
      } catch (err) {}
    }
    x += colWidths[0];

    const renderWrapped = (lines, width) => {
      lines.forEach((line, idx) => {
        doc.text(line, x + 1, y + 4 + idx * lineHeight);
      });
      x += width;
    };

    renderWrapped(wrappedSmiles, colWidths[1]);
    renderWrapped(wrappedVerdict, colWidths[2]);
    renderWrapped(wrappedEnergy, colWidths[3]);
    renderWrapped(wrappedMethod, colWidths[4]);
    renderWrapped(wrappedReason, colWidths[5]);

    doc.line(leftMargin, y + rowHeight, leftMargin + tableWidth, y + rowHeight);

    x = leftMargin;
    doc.line(x, y, x, y + rowHeight);
    colWidths.forEach((width) => {
      x += width;
      doc.line(x, y, x, y + rowHeight);
    });

    return rowHeight;
  };

  drawPageHeader();
  let y = tableTop;
  drawTableHeader(y);
  y += headerHeight;

  lastResults.forEach((row) => {
    const reason = (row.reasons && row.reasons.length
      ? row.reasons.join("; ")
      : (row.violations || []).join("; ") || "—"
    );

    const smiles = row.smiles ?? "—";
    const verdict = row.verdict ?? "—";
    const energy = (row.energy_kcal_mol ?? "—").toString();
    const method = row.classical_method ?? row.method ?? "—";

    const wrappedRowHeight = Math.max(
      wrapText(smiles, colWidths[1]).length,
      wrapText(verdict, colWidths[2]).length,
      wrapText(energy, colWidths[3]).length,
      wrapText(method, colWidths[4]).length,
      wrapText(reason, colWidths[5]).length,
      1
    ) * lineHeight + 2;
    const imageHeight = row.structure_png ? 12 : 0;
    const rowHeight = Math.max(wrappedRowHeight, imageHeight + 4);

    if (y + rowHeight > pageHeight - bottomMargin) {
      doc.addPage();
      drawPageHeader();
      y = tableTop;
      drawTableHeader(y);
      y += headerHeight;
    }

    const usedHeight = drawRow(y, {
      structurePng: row.structure_png || null,
      smiles,
      verdict,
      energy,
      method,
      reason,
    });
    y += usedHeight;
  });

  const totalPages = doc.getNumberOfPages();
  for (let i = 1; i <= totalPages; i += 1) {
    doc.setPage(i);
    doc.setFont("helvetica", "normal");
    doc.setFontSize(9);
    doc.setTextColor(120, 120, 120);
    doc.text(`Page ${i} of ${totalPages}`, pageWidth / 2, pageHeight - 8, { align: "center" });
  }

  doc.save("q-nexus-results.pdf");
};

// Execution log loader
const renderRuns = (runs) => {
  runsBody.innerHTML = "";
  if (!runs.length) {
    runsBody.innerHTML = "<tr><td class=\"px-4 py-4 text-center text-slate-500 text-xs\" colspan=\"3\">No execution logs found.</td></tr>";
    return;
  }

  runs.forEach((run) => {
    const tr = document.createElement("tr");
    tr.className = "cursor-pointer hover:bg-slate-900 border-b border-slate-900/60 transition";
    tr.innerHTML = `
      <td class="px-4 py-3 text-xs text-indigo-400 font-bold">#${run.id}</td>
      <td class="px-4 py-3 text-xs text-slate-300 font-medium">${new Date(run.created_at).toLocaleString()}</td>
      <td class="px-4 py-3 text-xs text-slate-400 text-center">${run.input_count}</td>
    `;
    tr.addEventListener("click", () => loadRun(run.id));
    runsBody.appendChild(tr);
  });
};

const loadRuns = async () => {
  try {
    const url = activeUser ? `/runs?username=${encodeURIComponent(activeUser)}` : "/runs";
    const response = await fetch(url);
    const runs = await response.json();
    renderRuns(runs);
  } catch (error) {
    setStatus("Unable to load execution history log.", "error");
  }
};

const loadRun = async (runId) => {
  try {
    const response = await fetch(`/runs/${runId}`);
    if (!response.ok) {
      throw new Error("Run not found");
    }
    const data = await response.json();
    selectedRun.innerHTML = `
      <div class="space-y-1 text-slate-300 font-medium">
        <p class="text-indigo-300 font-bold">ID: #${data.id}</p>
        <p>Molecules: ${data.input_count}</p>
        <p class="text-xxs text-slate-500">Date: ${new Date(data.created_at).toLocaleString()}</p>
      </div>
    `;
    renderResults(data.results || []);
  } catch (error) {
    setStatus("Unable to load selected execution run.", "error");
  }
};

// Main submit function
const runValidation = async (smilesList) => {
  if (!smilesList.length) {
    setStatus("Provide at least one SMILES string.", "error");
    return;
  }

  setStatus("Running symbolic constraint and quantum checks...");
  runBtn.disabled = true;

  try {
    const response = await fetch(apiUrl, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ smiles_list: smilesList, username: activeUser }),
    });

    if (!response.ok) {
      throw new Error(`API error: ${response.status}`);
    }

    const payload = await response.json();
    const results = payload.results || [];
    renderResults(results);
    if (payload.run_id) {
      selectedRun.innerHTML = `
        <div class="space-y-1 text-slate-300 font-medium">
          <p class="text-indigo-300 font-bold">ID: #${payload.run_id}</p>
          <p>Molecules: ${results.length}</p>
          <p class="text-xxs text-slate-500">Just Evaluated</p>
        </div>
      `;
    }
    await loadRuns();
    setStatus("Completed checks successfully.");
  } catch (error) {
    setStatus(`Cannot reach FastAPI backend server. Run: uvicorn app:app --reload (${error.message})`, "error");
  } finally {
    runBtn.disabled = false;
  }
};

// Event Listeners for running & clearing
runBtn.addEventListener("click", async () => {
  const textLines = smilesInput.value.split(/\r?\n/).map((line) => line.trim()).filter(Boolean);
  if (textLines.length) {
    await runValidation(textLines);
    return;
  }

  if (csvInput.files && csvInput.files[0]) {
    const smilesList = await parseCsvFirstColumn(csvInput.files[0]);
    await runValidation(smilesList);
    return;
  }

  setStatus("Add SMILES text inputs or drop a CSV file.", "error");
});

clearBtn.addEventListener("click", () => {
  smilesInput.value = "";
  csvInput.value = "";
  resultsBody.innerHTML = `<tr><td colspan="6" class="px-4 py-8 text-center text-slate-500 text-xs">No validation run completed. Enter SMILES and run pipeline above.</td></tr>`;
  passRateEl.textContent = "—";
  countEl.textContent = "—";
  selectedRun.textContent = "Click an execution row on the left to examine its full output payload.";
  updateCharts([]);
  setStatus("Cleared inputs and workspace.");
});

csvInput.addEventListener("change", async () => {
  if (!csvInput.files || !csvInput.files[0]) {
    return;
  }
  const smilesList = await parseCsvFirstColumn(csvInput.files[0]);
  if (smilesList.length) {
    smilesInput.value = smilesList.join("\n");
    setStatus(`Loaded ${smilesList.length} SMILES rows from CSV.`);
  } else {
    setStatus("CSV file has no readable entries.", "error");
  }
});

// AI Copilot Chat implementation
const appendChatMessage = (text, sender) => {
  const wrapper = document.createElement("div");
  wrapper.className = "flex items-start gap-2 " + (sender === "user" ? "justify-end" : "");
  
  const icon = sender === "user" 
    ? `<div class="h-6 w-6 rounded-full bg-indigo-600 text-white flex items-center justify-center text-xxs mt-0.5"><i class="fa-solid fa-user"></i></div>`
    : `<div class="h-6 w-6 rounded-full bg-indigo-500/20 text-indigo-300 flex items-center justify-center text-xxs mt-0.5"><i class="fa-solid fa-robot"></i></div>`;

  const bubbleClass = sender === "user" ? "chat-bubble-user" : "chat-bubble-bot";
  
  wrapper.innerHTML = sender === "user"
    ? `<div class="${bubbleClass} p-3 max-w-[85%] font-medium">${text}</div>${icon}`
    : `${icon}<div class="${bubbleClass} p-3 max-w-[85%] font-medium">${text}</div>`;

  chatMessages.appendChild(wrapper);
  chatMessages.scrollTop = chatMessages.scrollHeight;
};

const sendChatMessage = async (text) => {
  if (!text.trim()) return;
  appendChatMessage(text, "user");

  // Fetch API Key if configured
  const apiKey = sessionStorage.getItem("openai_api_key") || "";

  // Append a loader placeholder
  const loaderWrapper = document.createElement("div");
  loaderWrapper.className = "flex items-start gap-2";
  loaderWrapper.innerHTML = `
    <div class="h-6 w-6 rounded-full bg-indigo-500/20 text-indigo-300 flex items-center justify-center text-xxs mt-0.5"><i class="fa-solid fa-robot animate-pulse"></i></div>
    <div class="chat-bubble-bot p-3 max-w-[85%] font-medium text-slate-500 italic">Copilot is thinking...</div>
  `;
  chatMessages.appendChild(loaderWrapper);
  chatMessages.scrollTop = chatMessages.scrollHeight;

  try {
    const response = await fetch("/qa", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ query: text, api_key: apiKey }),
    });
    
    chatMessages.removeChild(loaderWrapper);

    if (!response.ok) {
      throw new Error(`Server returned code ${response.status}`);
    }

    const data = await response.json();
    const answer = data.answer || "No response received.";
    appendChatMessage(answer, "bot");
  } catch (error) {
    chatMessages.removeChild(loaderWrapper);
    appendChatMessage(`Sorry, I couldn't reach the chatbot API server: ${error.message}. Please verify the backend is running.`, "bot");
  }
};

// Form Send handler
sendChatBtn.addEventListener("click", () => {
  const text = chatInput.value;
  if (text.trim()) {
    sendChatMessage(text);
    chatInput.value = "";
  }
});

chatInput.addEventListener("keydown", (e) => {
  if (e.key === "Enter") {
    const text = chatInput.value;
    if (text.trim()) {
      sendChatMessage(text);
      chatInput.value = "";
    }
  }
});

// Suggestions dispatcher
window.sendSuggestion = (promptText) => {
  sendChatMessage(promptText);
};

// Auth event triggers
showAuthModalBtn.addEventListener("click", () => {
  authUsername.value = "";
  authPassword.value = "";
  authErrorMsg.classList.add("hidden");
  selectAuthTab("login");
  authModal.classList.remove("hidden");
});

closeAuthModalBtn.addEventListener("click", () => {
  authModal.classList.add("hidden");
});

tabLogin.addEventListener("click", () => selectAuthTab("login"));
tabRegister.addEventListener("click", () => selectAuthTab("register"));

authForm.addEventListener("submit", async (e) => {
  e.preventDefault();
  const username = authUsername.value.trim();
  const password = authPassword.value;
  if (!username || !password) return;

  authSubmitBtn.disabled = true;
  authErrorMsg.classList.add("hidden");

  const path = authMode === "login" ? "/login" : "/register";
  try {
    const response = await fetch(path, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ username, password }),
    });

    const data = await response.json();
    if (!response.ok) {
      throw new Error(data.detail || "Authentication failed");
    }

    if (authMode === "login") {
      activeUser = data.username;
      sessionStorage.setItem("active_user", activeUser);
      updateAuthStateUI();
      authModal.classList.add("hidden");
    } else {
      alert("Registration successful! Please login.");
      selectAuthTab("login");
      authPassword.value = "";
    }
  } catch (err) {
    authErrorMsg.textContent = err.message;
    authErrorMsg.classList.remove("hidden");
  } finally {
    authSubmitBtn.disabled = false;
  }
});

logoutBtn.addEventListener("click", () => {
  activeUser = null;
  sessionStorage.removeItem("active_user");
  updateAuthStateUI();
});

// Initial triggers
refreshRuns.addEventListener("click", loadRuns);
downloadPdf.addEventListener("click", exportPdf);

updateAuthStateUI();
