const apiUrl = "/validate_batch";

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

let lastResults = [];

const setStatus = (text, tone = "info") => {
  statusEl.textContent = text;
  statusEl.className = tone === "error" ? "text-sm text-rose-400" : "text-sm text-slate-400";
};

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

const renderResults = (results) => {
  resultsBody.innerHTML = "";
  lastResults = results;
  if (!results.length) {
    passRateEl.textContent = "—";
    countEl.textContent = "0";
    return;
  }

  const passCount = results.filter((row) => row.verdict === "PASS").length;
  const passRate = ((passCount / results.length) * 100).toFixed(1);
  passRateEl.textContent = `${passRate}%`;
  countEl.textContent = `${results.length}`;

  results.forEach((row) => {
    const tr = document.createElement("tr");
    const structureCell = row.structure_png
      ? `<img src="data:image/png;base64,${row.structure_png}" class="h-14 w-20 rounded-md bg-slate-950/40 object-contain" alt="structure" />`
      : `<span class="text-xs text-slate-500">—</span>`;

    tr.innerHTML = `
      <td class="px-3 py-3 text-xs text-slate-100">${structureCell}</td>
      <td class="px-3 py-3 text-xs text-slate-100">${row.smiles}</td>
      <td class="px-3 py-3">
        <span class="rounded-full px-2 py-1 text-xs ${row.verdict === "PASS" ? "bg-emerald-500/20 text-emerald-200" : row.verdict === "UNKNOWN" ? "bg-amber-500/20 text-amber-200" : "bg-rose-500/20 text-rose-200"}">
          ${row.verdict}
        </span>
      </td>
      <td class="px-3 py-3 text-xs text-slate-200">${row.energy_kcal_mol ?? "—"}</td>
      <td class="px-3 py-3 text-xs text-slate-300">${row.classical_method ?? row.method ?? "—"}</td>
      <td class="px-3 py-3 text-xs text-slate-400">${(row.reasons && row.reasons.length ? row.reasons : row.violations || []).join("; ")}</td>
    `;
    resultsBody.appendChild(tr);
  });
};

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

  // determine page background color from site (fallback white)
  const parseRgb = (rgbString) => {
    if (!rgbString) return [255, 255, 255];
    const m = rgbString.match(/rgba?\(([^)]+)\)/);
    if (!m) return [255, 255, 255];
    const parts = m[1].split(/,/).map((p) => p.trim());
    const r = parseInt(parts[0], 10) || 255;
    const g = parseInt(parts[1], 10) || 255;
    const b = parseInt(parts[2], 10) || 255;
    return [r, g, b];
  };

  const bodyBg = window.getComputedStyle(document.body).backgroundColor;
  const [pageBgR, pageBgG, pageBgB] = parseRgb(bodyBg);

  const drawPageHeader = () => {
    // fill page background to match the website
    doc.setFillColor(pageBgR, pageBgG, pageBgB);
    doc.rect(0, 0, pageWidth, pageHeight, "F");

    doc.setFont("helvetica", "bold");
    doc.setFontSize(16);
    doc.setTextColor(255 - Math.round(pageBgR * 0.8), 255 - Math.round(pageBgG * 0.8), 255 - Math.round(pageBgB * 0.8));
    doc.text("Q-NEXUS Validation Results", pageWidth / 2, topMargin + 6, { align: "center" });

    const now = new Date();
    const dateText = now.toLocaleDateString();
    const timeText = now.toLocaleTimeString([], { hour: "numeric", minute: "2-digit", second: "2-digit" });

    doc.setFont("helvetica", "normal");
    doc.setFontSize(9);
    // slightly muted text color for metadata
    doc.setTextColor(180, 180, 180);
    doc.text(`Date: ${dateText}`, leftMargin, topMargin + 14);
    doc.text(`Time: ${timeText}`, leftMargin, topMargin + 20);
    // reset text color for table drawing
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
      doc.addImage(imageData, "PNG", x + 2, y + 2, 16, 12);
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
    doc.setTextColor(0, 0, 0);
  }

  doc.save("q-nexus-results.pdf");
};

const renderRuns = (runs) => {
  runsBody.innerHTML = "";
  if (!runs.length) {
    runsBody.innerHTML = "<tr><td class=\"px-3 py-3 text-xs text-slate-400\" colspan=\"3\">No runs yet.</td></tr>";
    return;
  }

  runs.forEach((run) => {
    const tr = document.createElement("tr");
    tr.className = "cursor-pointer hover:bg-slate-800/40";
    tr.innerHTML = `
      <td class="px-3 py-3 text-xs text-emerald-300">#${run.id}</td>
      <td class="px-3 py-3 text-xs text-slate-200">${new Date(run.created_at).toLocaleString()}</td>
      <td class="px-3 py-3 text-xs text-slate-300">${run.input_count}</td>
    `;
    tr.addEventListener("click", () => loadRun(run.id));
    runsBody.appendChild(tr);
  });
};

const loadRuns = async () => {
  try {
    const response = await fetch("/runs");
    const runs = await response.json();
    renderRuns(runs);
  } catch (error) {
    setStatus("Unable to load run history.", "error");
  }
};

const loadRun = async (runId) => {
  try {
    const response = await fetch(`/runs/${runId}`);
    if (!response.ok) {
      throw new Error("Run not found");
    }
    const data = await response.json();
    selectedRun.textContent = `Run #${data.id} • ${new Date(data.created_at).toLocaleString()} • ${data.input_count} inputs`;
    renderResults(data.results || []);
  } catch (error) {
    setStatus("Unable to load selected run.", "error");
  }
};

const runValidation = async (smilesList) => {
  if (!smilesList.length) {
    setStatus("Provide at least one SMILES string.", "error");
    return;
  }

  setStatus("Running validation...");
  runBtn.disabled = true;

  try {
    const response = await fetch(apiUrl, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ smiles_list: smilesList }),
    });

    if (!response.ok) {
      throw new Error(`API error: ${response.status}`);
    }

    const payload = await response.json();
    const results = payload.results || [];
    renderResults(results);
    if (payload.run_id) {
      selectedRun.textContent = `Run #${payload.run_id} • just now`;
    }
    await loadRuns();
    setStatus("Completed.");
  } catch (error) {
    setStatus(`Cannot reach API. Start it with: uvicorn app:app --reload. (${error.message})`, "error");
  } finally {
    runBtn.disabled = false;
  }
};

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

  setStatus("Add SMILES text or upload CSV.", "error");
});

clearBtn.addEventListener("click", () => {
  smilesInput.value = "";
  csvInput.value = "";
  resultsBody.innerHTML = "";
  passRateEl.textContent = "—";
  countEl.textContent = "—";
  setStatus("Cleared.");
});

csvInput.addEventListener("change", async () => {
  if (!csvInput.files || !csvInput.files[0]) {
    return;
  }
  const smilesList = await parseCsvFirstColumn(csvInput.files[0]);
  if (smilesList.length) {
    smilesInput.value = smilesList.join("\n");
    setStatus(`Loaded ${smilesList.length} SMILES from CSV.`);
  } else {
    setStatus("CSV has no usable rows.", "error");
  }
});

refreshRuns.addEventListener("click", loadRuns);
downloadPdf.addEventListener("click", exportPdf);

loadRuns();
