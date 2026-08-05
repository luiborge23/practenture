"use strict";

function wsElement(tag, className = "", value = "") {
  const element = document.createElement(tag);
  if (className) element.className = className;
  if (value !== "") element.textContent = String(value);
  return element;
}

function wsDate(value) {
  if (!value) return "—";
  const parsed = new Date(value);
  return Number.isNaN(parsed.valueOf()) ? String(value) : parsed.toLocaleString();
}

function wsField(label, name, options = {}) {
  const wrapper = wsElement("label", "field");
  const caption = wsElement("span", "field-label", label);
  let control;
  if (options.options) {
    control = document.createElement("select");
    for (const [value, textValue] of options.options) {
      const option = document.createElement("option");
      option.value = value;
      option.textContent = textValue;
      control.append(option);
    }
  } else if (options.multiline) {
    control = document.createElement("textarea");
    control.rows = options.rows || 3;
  } else {
    control = document.createElement("input");
    control.type = options.type || "text";
  }
  control.name = name;
  if (options.value !== undefined && options.value !== null) control.value = options.value;
  if (options.placeholder) control.placeholder = options.placeholder;
  if (options.readOnly) control.readOnly = true;
  if (options.required) control.required = true;
  if (options.minLength) control.minLength = options.minLength;
  if (options.maxLength) control.maxLength = options.maxLength;
  if (options.min !== undefined) control.min = String(options.min);
  if (options.max !== undefined) control.max = String(options.max);
  if (options.step !== undefined) control.step = String(options.step);
  if (options.autocomplete) control.autocomplete = options.autocomplete;
  if (options.suggestions && control instanceof HTMLInputElement) {
    const list = document.createElement("datalist");
    list.id = `suggestions-${name}-${globalThis.crypto?.randomUUID?.() || Date.now()}`;
    wsReplaceSuggestions(list, options.suggestions);
    control.setAttribute("list", list.id);
    if (options.onSuggestionInput) control.addEventListener("input", () => options.onSuggestionInput(control.value, list));
    wrapper.append(caption, control, list);
    return wrapper;
  }
  wrapper.append(caption, control);
  return wrapper;
}

function wsDialog({ title, description = "", fields = [], submitLabel = "Save", danger = false }) {
  return new Promise((resolve) => {
    const dialog = document.createElement("dialog");
    const form = wsElement("form", "dialog-card stack");
    form.method = "dialog";
    form.append(wsElement("h2", "", title));
    if (description) form.append(wsElement("p", "muted", description));
    for (const field of fields) form.append(wsField(field.label, field.name, field));
    const actions = wsElement("div", "button-row");
    const cancel = button("Cancel");
    const submit = button(submitLabel, danger ? "button-danger" : "button-primary");
    submit.type = "submit";
    actions.append(cancel, submit);
    form.append(actions);
    dialog.append(form);
    document.body.append(dialog);
    let settled = false;
    const finish = (value) => {
      if (settled) return;
      settled = true;
      dialog.close();
      dialog.remove();
      resolve(value);
    };
    cancel.addEventListener("click", () => finish(null));
    dialog.addEventListener("cancel", (event) => {
      event.preventDefault();
      finish(null);
    });
    form.addEventListener("submit", (event) => {
      event.preventDefault();
      const values = Object.fromEntries(new FormData(form).entries());
      finish(values);
    });
    dialog.showModal();
    form.querySelector("input,select,textarea")?.focus();
  });
}

function wsShowRecoveryCodes(codes, title = "Save your recovery codes") {
  return new Promise((resolve) => {
    const dialog = document.createElement("dialog");
    const panel = wsElement("section", "dialog-card stack");
    panel.append(
      wsElement("h2", "", title),
      wsElement("p", "muted", "Each code works once. Store them in a password manager now; Practenture stores only one-way hashes and cannot show these codes again."),
    );
    const output = document.createElement("textarea");
    output.className = "secret-output";
    output.readOnly = true;
    output.rows = Math.min(12, Math.max(6, codes.length));
    output.spellcheck = false;
    output.value = codes.join("\n");
    output.setAttribute("aria-label", "Administrator MFA recovery codes");
    const copy = button("Copy recovery codes");
    const copyStatus = wsElement("p", "muted");
    copyStatus.setAttribute("aria-live", "polite");
    copy.addEventListener("click", async () => {
      try {
        await navigator.clipboard.writeText(output.value);
        copyStatus.textContent = "Recovery codes copied. Store them securely.";
      } catch {
        output.focus();
        output.select();
        copyStatus.textContent = "Copy was unavailable. Select and copy the codes manually.";
      }
    });
    const acknowledgement = wsElement("label", "field");
    const checkbox = document.createElement("input");
    checkbox.type = "checkbox";
    acknowledgement.append(checkbox, document.createTextNode(" I saved these one-time recovery codes securely."));
    const close = button("Finish MFA setup", "button-primary");
    close.disabled = true;
    checkbox.addEventListener("change", () => { close.disabled = !checkbox.checked; });
    const finish = () => {
      if (!checkbox.checked) return;
      output.value = "";
      dialog.close();
      dialog.remove();
      resolve();
    };
    close.addEventListener("click", finish);
    dialog.addEventListener("cancel", (event) => event.preventDefault());
    panel.append(output, copy, copyStatus, acknowledgement, close);
    dialog.append(panel);
    document.body.append(dialog);
    dialog.showModal();
    output.focus();
  });
}

function wsConfirmMfaEnrollment(enrollment) {
  return new Promise((resolve) => {
    const dialog = document.createElement("dialog");
    const form = wsElement("form", "dialog-card stack");
    const qr = document.createElement("img");
    qr.src = enrollment.qrCodeDataUri;
    qr.alt = "QR code for the Practenture Administrator authenticator account";
    const secret = document.createElement("textarea");
    secret.className = "secret-output";
    secret.readOnly = true;
    secret.rows = 2;
    secret.spellcheck = false;
    secret.value = enrollment.secret;
    secret.setAttribute("aria-label", "Manual authenticator setup key");
    const codeField = wsField("Six-digit code from your authenticator", "code", {
      required: true,
      minLength: 6,
      maxLength: 64,
      autocomplete: "one-time-code",
    });
    const codeInput = codeField.querySelector("input");
    codeInput.inputMode = "numeric";
    const error = wsElement("div", "alert alert-error");
    error.hidden = true;
    error.setAttribute("role", "alert");
    const actions = wsElement("div", "button-row");
    const cancel = button("Cancel");
    const confirm = button("Verify and enable MFA", "button-primary");
    confirm.type = "submit";
    actions.append(cancel, confirm);
    form.append(
      wsElement("h2", "", "Set up Administrator MFA"),
      wsElement("p", "muted", "Scan this QR code with your authenticator app, or enter the setup key manually. MFA remains disabled until the first code is verified."),
      qr,
      wsElement("p", "field-label", "Manual setup key"),
      secret,
      codeField,
      error,
      actions,
    );
    const finish = (value) => {
      secret.value = "";
      dialog.close();
      dialog.remove();
      resolve(value);
    };
    cancel.addEventListener("click", () => finish(null));
    dialog.addEventListener("cancel", (event) => { event.preventDefault(); finish(null); });
    form.addEventListener("submit", async (event) => {
      event.preventDefault();
      confirm.disabled = true;
      error.hidden = true;
      try {
        const result = await request("/auth/mfa/confirm", {
          method: "POST",
          body: JSON.stringify({ code: codeInput.value.trim() }),
        });
        finish(result.recoveryCodes);
      } catch (failure) {
        error.textContent = failure.message;
        error.hidden = false;
        confirm.disabled = false;
        codeInput.focus();
      }
    });
    dialog.append(form);
    document.body.append(dialog);
    dialog.showModal();
    codeInput.focus();
  });
}

function wsTable(columns, rows, rowActions) {
  if (!rows.length) return $("empty-template").content.cloneNode(true);
  const card = wsElement("div", "table-card");
  const scroll = wsElement("div", "table-scroll");
  const table = document.createElement("table");
  const head = document.createElement("thead");
  const headRow = document.createElement("tr");
  for (const column of columns) {
    const cell = wsElement("th", "", column.label);
    cell.scope = "col";
    headRow.append(cell);
  }
  if (rowActions) {
    const cell = wsElement("th", "", "Actions");
    cell.scope = "col";
    headRow.append(cell);
  }
  head.append(headRow);
  const body = document.createElement("tbody");
  for (const row of rows) {
    const tableRow = document.createElement("tr");
    for (const column of columns) {
      const cell = document.createElement("td");
      cell.dataset.label = column.label;
      const value = column.value(row);
      if (column.badge) cell.append(badge(value));
      else cell.textContent = value === null || value === undefined || value === "" ? "—" : String(value);
      tableRow.append(cell);
    }
    if (rowActions) {
      const cell = document.createElement("td");
      cell.dataset.label = "Actions";
      const actions = wsElement("div", "button-row compact");
      rowActions(row, actions);
      cell.append(actions);
      tableRow.append(cell);
    }
    body.append(tableRow);
  }
  table.append(head, body);
  scroll.append(table);
  card.append(scroll);
  return card;
}

function wsToolbar() {
  return wsElement("div", "workspace-toolbar");
}

function wsFilters(fields, onSubmit) {
  const form = wsElement("form", "card filter-grid");
  for (const field of fields) form.append(wsField(field.label, field.name, field));
  const actions = wsElement("div", "button-row filter-actions");
  const apply = button("Apply filters", "button-primary");
  apply.type = "submit";
  const reset = button("Reset");
  actions.append(reset, apply);
  form.append(actions);
  form.addEventListener("submit", (event) => {
    event.preventDefault();
    onSubmit(Object.fromEntries(new FormData(form).entries()));
  });
  reset.addEventListener("click", () => {
    form.reset();
    onSubmit({});
  });
  return form;
}

function wsPagination({ pageInfo = {}, totalCount = null, visibleCount = 0, cursor = null, trail = [], onPage }) {
  const bar = wsElement("nav", "pagination-bar");
  bar.setAttribute("aria-label", "Result pages");
  const hasTotal = Number.isFinite(totalCount);
  const summary = wsElement("span", "muted", hasTotal ? `${visibleCount} shown · ${totalCount} total` : `${visibleCount} shown on this page`);
  const actions = wsElement("div", "button-row compact");
  const previous = button("Previous");
  const next = button("Next");
  previous.disabled = trail.length === 0;
  const hasNext = pageInfo.hasNextPage ?? pageInfo.hasMore ?? false;
  next.disabled = !hasNext || !pageInfo.nextCursor;
  previous.addEventListener("click", () => {
    if (!trail.length) return;
    onPage(trail.at(-1) || null, trail.slice(0, -1));
  });
  next.addEventListener("click", () => {
    if (!pageInfo.nextCursor) return;
    onPage(pageInfo.nextCursor, [...trail, cursor]);
  });
  actions.append(previous, next);
  bar.append(summary, actions);
  return bar;
}

function wsAddCursor(query, cursor) {
  if (cursor) query.set("cursor", cursor);
  return query;
}

function wsReplaceSuggestions(list, rows) {
  list.replaceChildren();
  for (const row of rows) {
    const option = document.createElement("option");
    option.value = row.id;
    option.label = [row.name, row.universityName].filter(Boolean).join(" · ");
    list.append(option);
  }
}

async function wsRecentMutation(path, options = {}) {
  await reauthenticate();
  const method = options.method || "POST";
  const headers = { "Idempotency-Key": idempotencyKey(), ...(options.headers || {}) };
  return request(path, { method, headers, body: JSON.stringify(options.body || {}) });
}

async function renderOrganizationsWorkspace(filters = {}, cursor = null, trail = []) {
  loading();
  notice("");
  try {
    const query = wsAddCursor(new URLSearchParams({ limit: "25" }), cursor);
    if (filters.search) query.set("search", filters.search);
    if (filters.status) query.set("status", filters.status);
    const data = await request(`/organizations?${query}`);
    const fragment = document.createDocumentFragment();
    const head = header("organizations");
    const create = button("Create organization", "button-primary");
    head.append(create);
    fragment.append(head);
    fragment.append(wsFilters([
      { label: "Search", name: "search", value: filters.search || "", placeholder: "Name, university, or slug" },
      { label: "Status", name: "status", value: filters.status || "", options: [["", "All statuses"], ["active", "Active"], ["inactive", "Inactive"]] },
    ], (nextFilters) => renderOrganizationsWorkspace(nextFilters)));
    create.addEventListener("click", async () => {
      const values = await wsDialog({
        title: "Create organization",
        description: "Organizations isolate professor, student, and simulation data.",
        submitLabel: "Create organization",
        fields: [
          { label: "Organization name", name: "name", required: true, maxLength: 200 },
          { label: "University name (optional)", name: "universityName", maxLength: 300 },
          { label: "Slug (optional)", name: "slug", maxLength: 100, placeholder: "generated-from-name" },
        ],
      });
      if (!values) return;
      try {
        const body = { name: values.name.trim() };
        if (values.universityName.trim()) body.universityName = values.universityName.trim();
        if (values.slug.trim()) body.slug = values.slug.trim();
        await request("/organizations", { method: "POST", headers: { "Idempotency-Key": idempotencyKey() }, body: JSON.stringify(body) });
        await renderOrganizationsWorkspace(filters);
        notice("Organization created.");
      } catch (error) { notice(error.message, true); }
    });
    const table = wsTable([
      { label: "Organization", value: (row) => row.name },
      { label: "University", value: (row) => row.universityName },
      { label: "Status", value: (row) => row.status, badge: true },
      { label: "Professors", value: (row) => row.professorCount },
      { label: "Students", value: (row) => row.studentCount },
      { label: "Sessions", value: (row) => row.sessionCount },
    ], data.organizations || [], (organization, actions) => {
      const edit = button("Edit");
      edit.addEventListener("click", async () => {
        const values = await wsDialog({
          title: `Edit ${organization.name}`,
          submitLabel: "Save changes",
          fields: [
            { label: "Organization name", name: "name", required: true, value: organization.name, maxLength: 200 },
            { label: "University name", name: "universityName", value: organization.universityName || "", maxLength: 300 },
            { label: "Status", name: "status", value: organization.status, options: [["active", "Active"], ["inactive", "Inactive"]] },
          ],
        });
        if (!values) return;
        edit.disabled = true;
        try {
          await request(`/organizations/${encodeURIComponent(organization.id)}`, {
            method: "PATCH",
            headers: { "If-Match": `"${organization.version}"`, "Idempotency-Key": idempotencyKey() },
            body: JSON.stringify({ name: values.name.trim(), universityName: values.universityName.trim() || null, status: values.status }),
          });
          await renderOrganizationsWorkspace(filters);
          notice("Organization updated.");
        } catch (error) { notice(error.message, true); }
        finally { edit.disabled = false; }
      });
      actions.append(edit);
    });
    fragment.append(table, wsPagination({
      pageInfo: data.pageInfo,
      totalCount: data.totalCount,
      visibleCount: (data.organizations || []).length,
      cursor,
      trail,
      onPage: (nextCursor, nextTrail) => renderOrganizationsWorkspace(filters, nextCursor, nextTrail),
    }));
    page.replaceChildren(fragment);
    status(`${data.totalCount || 0} organizations loaded`);
  } catch (error) { renderError("organizations", error); }
  finally { page.setAttribute("aria-busy", "false"); }
}

async function renderUsersWorkspace(filters = {}, cursor = null, trail = []) {
  loading();
  notice("");
  try {
    const query = wsAddCursor(new URLSearchParams({ limit: "25" }), cursor);
    for (const key of ["search", "role", "status", "organizationId"]) if (filters[key]) query.set(key, filters[key]);
    const [data, organizationData] = await Promise.all([
      request(`/users?${query}`),
      request("/organizations?limit=25"),
    ]);
    const organizations = organizationData.organizations || [];
    const fragment = document.createDocumentFragment();
    const head = header("users");
    const invite = wsElement("a", "button button-primary", "Invite professor");
    invite.href = "#invitations";
    head.append(invite);
    fragment.append(head, wsFilters([
      { label: "Search", name: "search", value: filters.search || "", placeholder: "Username, name, or email" },
      { label: "Role", name: "role", value: filters.role || "", options: [["", "All roles"], ["owner", "Administrator"], ["professor", "Professor"], ["student", "Student"]] },
      { label: "Status", name: "status", value: filters.status || "", options: [["", "All statuses"], ["active", "Active"], ["suspended", "Suspended"]] },
      { label: "Organization", name: "organizationId", value: filters.organizationId || "", placeholder: "Search or paste organization ID", suggestions: organizations, onSuggestionInput: wsOrganizationSuggestionLoader() },
    ], (nextFilters) => renderUsersWorkspace(nextFilters)));
    const usersTable = wsTable([
      { label: "Username", value: (row) => row.username },
      { label: "Name", value: (row) => row.name },
      { label: "Email", value: (row) => row.email },
      { label: "Role", value: (row) => sessionRoleLabel(row.role), badge: true },
      { label: "Status", value: (row) => row.status, badge: true },
      { label: "Last sign-in", value: (row) => wsDate(row.lastLoginAt) },
    ], data.users || [], (user, actions) => {
      const details = button("Details");
      details.addEventListener("click", () => wsDialog({
        title: user.username,
        description: `${sessionRoleLabel(user.role)} account details`,
        submitLabel: "Close",
        fields: [
          { label: "Email", name: "email", value: user.email || "Not provided", readOnly: true },
          { label: "Provider", name: "provider", value: user.provider || "password", readOnly: true },
          { label: "Organizations", name: "organizations", value: (user.organizationIds || []).join(", ") || "None", readOnly: true },
          { label: "Password reset required", name: "reset", value: user.mustChangePassword ? "Yes" : "No", readOnly: true },
        ],
      }));
      actions.append(details);
      if (user.role !== "owner") {
        const lifecycle = button(user.status === "active" ? "Suspend" : "Reactivate", user.status === "active" ? "button-danger" : "button-secondary");
        lifecycle.addEventListener("click", async () => {
          const action = user.status === "active" ? "suspend" : "reactivate";
          const values = await wsDialog({
            title: `${titleCase(action)} ${user.username}`,
            description: action === "suspend" ? "Suspension revokes active sessions immediately." : "Reactivation restores account access.",
            submitLabel: titleCase(action),
            danger: action === "suspend",
            fields: [{ label: "Reason", name: "reason", multiline: true, required: action === "suspend", maxLength: 1000 }],
          });
          if (!values) return;
          lifecycle.disabled = true;
          try {
            await wsRecentMutation(`/users/${encodeURIComponent(user.id)}/${action}`, { body: { reason: values.reason.trim() || null } });
            await renderUsersWorkspace(filters);
            notice(`User ${action === "suspend" ? "suspended" : "reactivated"}.`);
          } catch (error) { if (!/cancelled/i.test(error.message)) notice(error.message, true); }
          finally { lifecycle.disabled = false; }
        });
        const sessions = button("Revoke sessions");
        sessions.addEventListener("click", async () => {
          if (!confirm(`Revoke every active session for ${user.username}?`)) return;
          sessions.disabled = true;
          try {
            await wsRecentMutation(`/users/${encodeURIComponent(user.id)}/revoke-sessions`, { body: { reason: "Administrator revoked sessions" } });
            notice("User sessions revoked.");
          } catch (error) { if (!/cancelled/i.test(error.message)) notice(error.message, true); }
          finally { sessions.disabled = false; }
        });
        const reset = button("Require password reset");
        reset.addEventListener("click", async () => {
          if (!confirm(`Require a password reset for ${user.username}?`)) return;
          reset.disabled = true;
          try {
            await wsRecentMutation(`/users/${encodeURIComponent(user.id)}/require-password-reset`, { body: { reason: "Administrator required password reset" } });
            await renderUsersWorkspace(filters);
            notice("Password reset requirement applied.");
          } catch (error) { if (!/cancelled/i.test(error.message)) notice(error.message, true); }
          finally { reset.disabled = false; }
        });
        actions.append(lifecycle, sessions, reset);
      }
    });
    usersTable.classList.add("users-table");
    fragment.append(usersTable, wsPagination({
      pageInfo: data.pageInfo,
      totalCount: data.totalCount,
      visibleCount: (data.users || []).length,
      cursor,
      trail,
      onPage: (nextCursor, nextTrail) => renderUsersWorkspace(filters, nextCursor, nextTrail),
    }));
    page.replaceChildren(fragment);
    status(`${data.totalCount || 0} users loaded`);
  } catch (error) { renderError("users", error); }
  finally { page.setAttribute("aria-busy", "false"); }
}

function wsOrganizationSuggestionLoader() {
  let timer = null;
  let sequence = 0;
  return (value, list) => {
    clearTimeout(timer);
    const current = ++sequence;
    timer = setTimeout(async () => {
      try {
        const query = new URLSearchParams({ limit: "25" });
        if (value.trim()) query.set("search", value.trim());
        const data = await request(`/organizations?${query}`);
        if (current === sequence) wsReplaceSuggestions(list, data.organizations || []);
      } catch {
        // Keep the last valid suggestions. Form submission still validates the ID server-side.
      }
    }, 250);
  };
}

async function renderInvitationsWorkspace(filters = {}, cursor = null, trail = []) {
  loading();
  notice("");
  try {
    const query = wsAddCursor(new URLSearchParams({ limit: "25" }), cursor);
    for (const key of ["search", "organizationId", "status"]) if (filters[key]) query.set(key, filters[key]);
    const [data, organizationData] = await Promise.all([
      request(`/invitations?${query}`),
      request("/organizations?limit=25"),
    ]);
    const organizations = organizationData.organizations || [];
    const fragment = document.createDocumentFragment();
    const head = header("invitations");
    const create = button("Create professor access", "button-primary");
    head.append(create);
    fragment.append(head, wsFilters([
      { label: "Search", name: "search", value: filters.search || "", placeholder: "Professor email, code, notes, or ticket" },
      { label: "Organization", name: "organizationId", value: filters.organizationId || "", placeholder: "Search or paste organization ID", suggestions: organizations, onSuggestionInput: wsOrganizationSuggestionLoader() },
      { label: "Status", name: "status", value: filters.status || "", options: [["", "All statuses"], ["ACTIVE", "Active"], ["REDEEMED", "Redeemed"], ["EXPIRED", "Expired"], ["REVOKED", "Revoked"]] },
    ], (nextFilters) => renderInvitationsWorkspace(nextFilters)));

    create.addEventListener("click", async () => {
      const values = await wsDialog({
        title: "Create professor access",
        description: "Create a one-time code bound to the professor’s exact email and organization.",
        submitLabel: "Create access",
        fields: [
          { label: "Organization", name: "organizationId", required: true, maxLength: 255, placeholder: "Search or paste organization ID", suggestions: organizations, onSuggestionInput: wsOrganizationSuggestionLoader() },
          { label: "Professor email", name: "intendedEmail", type: "email", autocomplete: "email", required: true, maxLength: 320 },
          { label: "Expires after (hours)", name: "expiresInHours", type: "number", value: "48", min: 1, max: 720, required: true },
          { label: "Internal notes", name: "notes", multiline: true, maxLength: 1000 },
          { label: "Change ticket", name: "changeTicket", maxLength: 255 },
        ],
      });
      if (!values) return;
      create.disabled = true;
      try {
        const result = await mutateInvitation("/invitations", {
          organizationId: values.organizationId.trim(),
          intendedEmail: values.intendedEmail.trim().toLowerCase(),
          expiresInHours: Number(values.expiresInHours),
          notes: values.notes.trim() || null,
          changeTicket: values.changeTicket.trim() || null,
        });
        revealInvitation(result.secret, result.invitation.intendedEmail, result.invitation.id);
        await renderInvitationsWorkspace(filters);
        notice("Professor access created. Complete the secure handoff before closing the code.");
      } catch (error) { if (!/cancelled/i.test(error.message)) notice(error.message, true); }
      finally { create.disabled = false; }
    });

    const table = wsTable([
      { label: "Professor email", value: (row) => row.intendedEmail },
      { label: "Organization", value: (row) => row.organizationId },
      { label: "Status", value: (row) => row.status, badge: true },
      { label: "Expires", value: (row) => wsDate(row.expiresAt) },
      { label: "Code", value: (row) => row.maskedCode },
    ], data.invitations || [], (invitation, actions) => {
      const details = button("Details");
      details.addEventListener("click", async () => {
        details.disabled = true;
        try {
          const result = await request(`/invitations/${encodeURIComponent(invitation.id)}`);
          const current = result.invitation;
          await wsDialog({
            title: current.intendedEmail,
            description: "Invitation secrets are never returned by list or detail requests.",
            submitLabel: "Close",
            fields: [
              { label: "Organization", name: "organization", value: current.organizationId, readOnly: true },
              { label: "Status", name: "status", value: current.status, readOnly: true },
              { label: "Created", name: "created", value: wsDate(current.createdAt), readOnly: true },
              { label: "Expires", name: "expires", value: wsDate(current.expiresAt), readOnly: true },
              { label: "Redeemed", name: "redeemed", value: wsDate(current.redeemedAt), readOnly: true },
              { label: "Revoked", name: "revoked", value: wsDate(current.revokedAt), readOnly: true },
              { label: "Notes", name: "notes", value: current.notes || "None", multiline: true, readOnly: true },
              { label: "Change ticket", name: "ticket", value: current.changeTicket || "None", readOnly: true },
            ],
          });
        } catch (error) { notice(error.message, true); }
        finally { details.disabled = false; }
      });
      actions.append(details);
      if (invitation.status === "ACTIVE") {
        const replace = button("Generate replacement");
        replace.addEventListener("click", async () => {
          if (!confirm(`Generate a replacement code for ${invitation.intendedEmail}? The current code will stop working.`)) return;
          replace.disabled = true;
          try {
            const result = await mutateInvitation(`/invitations/${encodeURIComponent(invitation.id)}/resend`, { expiresInHours: 48 });
            revealInvitation(result.secret, result.invitation.intendedEmail, result.invitation.id);
            await renderInvitationsWorkspace(filters);
            notice("Replacement access created. The previous code is no longer valid.");
          } catch (error) { if (!/cancelled/i.test(error.message)) notice(error.message, true); }
          finally { replace.disabled = false; }
        });
        const revoke = button("Revoke", "button-danger");
        revoke.addEventListener("click", async () => {
          const values = await wsDialog({
            title: `Revoke access for ${invitation.intendedEmail}`,
            description: "The professor will no longer be able to redeem this code.",
            submitLabel: "Revoke access",
            danger: true,
            fields: [{ label: "Reason", name: "reason", multiline: true, maxLength: 1000 }],
          });
          if (!values) return;
          revoke.disabled = true;
          try {
            await mutateInvitation(`/invitations/${encodeURIComponent(invitation.id)}/revoke`, { reason: values.reason.trim() || null });
            await renderInvitationsWorkspace(filters);
            notice("Professor access revoked.");
          } catch (error) { if (!/cancelled/i.test(error.message)) notice(error.message, true); }
          finally { revoke.disabled = false; }
        });
        actions.append(replace, revoke);
      }
    });
    table.classList.add("invitations-table");
    fragment.append(table, wsPagination({
      pageInfo: data.pageInfo,
      totalCount: data.totalCount,
      visibleCount: (data.invitations || []).length,
      cursor,
      trail,
      onPage: (nextCursor, nextTrail) => renderInvitationsWorkspace(filters, nextCursor, nextTrail),
    }));
    page.replaceChildren(fragment);
    status(`${data.totalCount || 0} professor invitations loaded`);
  } catch (error) { renderError("invitations", error); }
  finally { page.setAttribute("aria-busy", "false"); }
}

function wsSessionFilters(filters) {
  const result = {};
  for (const key of ["search", "state", "organizationId", "professorUserId", "scenarioId", "classId"]) if (filters[key]) result[key] = filters[key];
  for (const key of ["createdFrom", "createdTo"]) {
    if (filters[key]) result[key] = new Date(filters[key]).toISOString();
  }
  return result;
}

async function renderSessionsWorkspace(filters = {}, cursor = null, trail = []) {
  loading();
  notice("");
  try {
    const query = wsAddCursor(new URLSearchParams({ limit: "25" }), cursor);
    for (const [key, value] of Object.entries(wsSessionFilters(filters))) query.set(key, value);
    const [data, organizationData] = await Promise.all([
      request(`/sessions?${query}`),
      request("/organizations?limit=25"),
    ]);
    const organizations = organizationData.organizations || [];
    const fragment = document.createDocumentFragment();
    fragment.append(header("sessions"), wsFilters([
      { label: "Search", name: "search", value: filters.search || "", placeholder: "Code, professor, class, organization, or scenario" },
      { label: "State", name: "state", value: filters.state || "", placeholder: "active, completed, …" },
      { label: "Organization", name: "organizationId", value: filters.organizationId || "", placeholder: "Search or paste organization ID", suggestions: organizations, onSuggestionInput: wsOrganizationSuggestionLoader() },
      { label: "Professor user ID", name: "professorUserId", value: filters.professorUserId || "" },
      { label: "Scenario ID", name: "scenarioId", value: filters.scenarioId || "" },
      { label: "Class ID", name: "classId", value: filters.classId || "" },
      { label: "Created from", name: "createdFrom", type: "datetime-local", value: filters.createdFrom || "" },
      { label: "Created to", name: "createdTo", type: "datetime-local", value: filters.createdTo || "" },
    ], (nextFilters) => renderSessionsWorkspace(nextFilters)));
    const table = wsTable([
      { label: "Code", value: (row) => row.code },
      { label: "State", value: (row) => row.state, badge: true },
      { label: "Professor", value: (row) => row.professor?.name || row.professor?.userId },
      { label: "Organization", value: (row) => (row.organizations || []).map((item) => item.name).join(", ") },
      { label: "Scenario", value: (row) => row.scenario?.id || row.scenarioId },
      { label: "Round", value: (row) => row.currentRound },
      { label: "Created", value: (row) => wsDate(row.createdAt) },
    ], data.items || [], (session, actions) => {
      const details = button("Inspect");
      details.addEventListener("click", async () => {
        details.disabled = true;
        try {
          const current = session;
          await wsDialog({
            title: `Session ${current.code}`,
            description: "Read-only operational detail. Simulation state remains backend-authoritative.",
            submitLabel: "Close",
            fields: [
              { label: "State", name: "state", value: current.state, readOnly: true },
              { label: "Professor", name: "professor", value: current.professor?.userId || "—", readOnly: true },
              { label: "Organization", name: "organization", value: (current.organizations || []).map((item) => item.name).join(", ") || "—", readOnly: true },
              { label: "Scenario", name: "scenario", value: current.scenario?.id || "—", readOnly: true },
              { label: "Current round", name: "round", value: String(current.currentRound ?? "—"), readOnly: true },
              { label: "Teams", name: "teams", value: String(current.teamSummary?.total ?? current.teams?.length ?? "—"), readOnly: true },
            ],
          });
        } catch (error) { notice(error.message, true); }
        finally { details.disabled = false; }
      });
      actions.append(details);
    });
    fragment.append(table, wsPagination({
      pageInfo: data.page,
      visibleCount: (data.items || []).length,
      cursor,
      trail,
      onPage: (nextCursor, nextTrail) => renderSessionsWorkspace(filters, nextCursor, nextTrail),
    }));
    page.replaceChildren(fragment);
    status(`${(data.items || []).length} sessions loaded on this page`);
  } catch (error) { renderError("sessions", error); }
  finally { page.setAttribute("aria-busy", "false"); }
}

function wsAuditFilters(filters) {
  const result = {};
  for (const key of ["search", "action", "outcome", "actorId", "targetType", "targetId"]) if (filters[key]) result[key] = filters[key];
  for (const key of ["occurredFrom", "occurredTo"]) {
    if (filters[key]) result[key] = new Date(filters[key]).toISOString();
  }
  return result;
}

async function wsDownloadAudit(format, filters) {
  await reauthenticate();
  const artifact = await request("/audit-events/exports", {
    method: "POST",
    headers: { "Idempotency-Key": idempotencyKey() },
    body: JSON.stringify({ format, filters: wsAuditFilters(filters) }),
  });
  const response = await fetch(`${API}/audit-events/exports/${encodeURIComponent(artifact.artifactId)}`, {
    credentials: "same-origin",
    cache: "no-store",
    headers: { Accept: format === "json" ? "application/json" : "text/csv" },
  });
  if (!response.ok) throw new Error("The audit export could not be downloaded.");
  const blob = await response.blob();
  const url = URL.createObjectURL(blob);
  const anchor = document.createElement("a");
  anchor.href = url;
  anchor.download = artifact.fileName;
  document.body.append(anchor);
  anchor.click();
  anchor.remove();
  URL.revokeObjectURL(url);
  return artifact;
}

async function renderAuditWorkspace(filters = {}, cursor = null, trail = []) {
  loading();
  notice("");
  try {
    const query = wsAddCursor(new URLSearchParams({ limit: "25", sort: "occurredAt", sortDirection: "desc" }), cursor);
    for (const [key, value] of Object.entries(wsAuditFilters(filters))) query.set(key, value);
    const data = await request(`/audit-events?${query}`);
    const fragment = document.createDocumentFragment();
    const head = header("audit");
    const jsonExport = button("Export JSON");
    const csvExport = button("Export CSV", "button-primary");
    for (const [control, format] of [[jsonExport, "json"], [csvExport, "csv"]]) {
      control.addEventListener("click", async () => {
        control.disabled = true;
        try {
          const artifact = await wsDownloadAudit(format, filters);
          notice(`Downloaded ${artifact.rowCount} redacted audit events.`);
        } catch (error) { if (!/cancelled/i.test(error.message)) notice(error.message, true); }
        finally { control.disabled = false; }
      });
    }
    head.append(jsonExport, csvExport);
    fragment.append(head, wsFilters([
      { label: "Search", name: "search", value: filters.search || "", placeholder: "Actor, target, action, or request" },
      { label: "Action", name: "action", value: filters.action || "", placeholder: "admin.auth.login" },
      { label: "Outcome", name: "outcome", value: filters.outcome || "", options: [["", "All outcomes"], ["succeeded", "Succeeded"], ["accepted", "Accepted"], ["failed", "Failed"], ["denied", "Denied"]] },
      { label: "Actor ID", name: "actorId", value: filters.actorId || "" },
      { label: "Target type", name: "targetType", value: filters.targetType || "" },
      { label: "Target ID", name: "targetId", value: filters.targetId || "" },
      { label: "Occurred from", name: "occurredFrom", type: "datetime-local", value: filters.occurredFrom || "" },
      { label: "Occurred to", name: "occurredTo", type: "datetime-local", value: filters.occurredTo || "" },
    ], (nextFilters) => renderAuditWorkspace(nextFilters)));
    const table = wsTable([
      { label: "Time", value: (row) => wsDate(row.occurredAt) },
      { label: "Action", value: (row) => row.action },
      { label: "Outcome", value: (row) => row.outcome, badge: true },
      { label: "Actor", value: (row) => row.actor?.id || row.actor?.type },
      { label: "Target", value: (row) => row.target?.id || row.target?.type },
      { label: "Request", value: (row) => row.requestId },
    ], data.items || [], (event, actions) => {
      const details = button("Details");
      details.addEventListener("click", async () => {
        details.disabled = true;
        try {
          const result = await request(`/audit-events/${encodeURIComponent(event.eventId)}`);
          const current = result.auditEvent || result;
          await wsDialog({
            title: current.action,
            description: "Secrets are redacted by the server before this event reaches the browser.",
            submitLabel: "Close",
            fields: [
              { label: "Event ID", name: "eventId", value: current.eventId, readOnly: true },
              { label: "Request ID", name: "requestId", value: current.requestId, readOnly: true },
              { label: "Outcome", name: "outcome", value: current.outcome, readOnly: true },
              { label: "Actor", name: "actor", multiline: true, value: JSON.stringify(current.actor, null, 2), readOnly: true },
              { label: "Target", name: "target", multiline: true, value: JSON.stringify(current.target, null, 2), readOnly: true },
              { label: "Metadata", name: "metadata", multiline: true, rows: 6, value: JSON.stringify(current.metadata, null, 2), readOnly: true },
            ],
          });
        } catch (error) { notice(error.message, true); }
        finally { details.disabled = false; }
      });
      actions.append(details);
    });
    fragment.append(table, wsPagination({
      pageInfo: data.page,
      visibleCount: (data.items || []).length,
      cursor,
      trail,
      onPage: (nextCursor, nextTrail) => renderAuditWorkspace(filters, nextCursor, nextTrail),
    }));
    page.replaceChildren(fragment);
    status(`${(data.items || []).length} audit events loaded on this page`);
  } catch (error) { renderError("audit", error); }
  finally { page.setAttribute("aria-busy", "false"); }
}

async function renderOperationsWorkspace(
  backupCursor = null,
  backupTrail = [],
  drillCursor = null,
  drillTrail = [],
) {
  loading();
  notice("");
  try {
    const backupQuery = wsAddCursor(new URLSearchParams({ limit: "25" }), backupCursor);
    const drillQuery = wsAddCursor(new URLSearchParams({ limit: "25" }), drillCursor);
    const [health, backups, drills] = await Promise.all([
      request("/operations/health"),
      request(`/operations/backups?${backupQuery}`),
      request(`/operations/restore-drills?${drillQuery}`),
    ]);
    const fragment = document.createDocumentFragment();
    const head = header("operations");
    const create = button("Create verified backup", "button-primary");
    create.addEventListener("click", async () => {
      const values = await wsDialog({
        title: "Create verified backup",
        description: "Practenture creates an online SQLite backup and immediately proves it with a disposable restore drill.",
        submitLabel: "Create and verify",
        fields: [{ label: "Label (optional)", name: "label", maxLength: 100 }],
      });
      if (!values) return;
      create.disabled = true;
      try {
        const result = await wsRecentMutation("/operations/backups", { body: values.label.trim() ? { label: values.label.trim() } : {} });
        await renderOperationsWorkspace();
        notice(`Backup ${result.backup?.id || "completed"} was created and verified.`);
      } catch (error) { if (!/cancelled/i.test(error.message)) notice(error.message, true); }
      finally { create.disabled = false; }
    });
    head.append(create);
    fragment.append(head);
    const summary = wsElement("div", "metric-grid");
    for (const [label, value] of [["Overall status", health.status], ["Passed checks", health.summary?.passed], ["Warnings", health.summary?.warnings], ["Failed checks", health.summary?.failed]]) {
      const card = wsElement("article", "metric");
      card.append(wsElement("span", "", label), wsElement("strong", "", value ?? 0));
      summary.append(card);
    }
    fragment.append(summary, wsElement("h2", "", "Health checks"));
    fragment.append(wsTable([
      { label: "Check", value: (row) => titleCase(row.code) },
      { label: "Status", value: (row) => row.status, badge: true },
      { label: "Severity", value: (row) => row.severity },
      { label: "Details", value: (row) => row.details ? JSON.stringify(row.details) : "—" },
      { label: "Affected", value: (row) => row.affectedCount },
    ], health.checks || []));
    fragment.append(wsElement("h2", "section-title", "Verified backups"));
    fragment.append(wsTable([
      { label: "Started", value: (row) => wsDate(row.startedAt) },
      { label: "Status", value: (row) => row.status, badge: true },
      { label: "Label", value: (row) => row.label },
      { label: "Bytes", value: (row) => row.databaseSize },
      { label: "SHA-256", value: (row) => row.sha256 },
    ], backups.items || []), wsPagination({
      pageInfo: backups.pageInfo,
      totalCount: backups.totalCount,
      visibleCount: (backups.items || []).length,
      cursor: backupCursor,
      trail: backupTrail,
      onPage: (nextCursor, nextTrail) => renderOperationsWorkspace(nextCursor, nextTrail, drillCursor, drillTrail),
    }));
    fragment.append(wsElement("h2", "section-title", "Restore drills"));
    fragment.append(wsTable([
      { label: "Completed", value: (row) => wsDate(row.endedAt) },
      { label: "Status", value: (row) => row.status, badge: true },
      { label: "Backup", value: (row) => row.backupId },
      { label: "Error", value: (row) => row.errorMessage },
    ], drills.items || []), wsPagination({
      pageInfo: drills.pageInfo,
      totalCount: drills.totalCount,
      visibleCount: (drills.items || []).length,
      cursor: drillCursor,
      trail: drillTrail,
      onPage: (nextCursor, nextTrail) => renderOperationsWorkspace(backupCursor, backupTrail, nextCursor, nextTrail),
    }));
    page.replaceChildren(fragment);
    status("Operations loaded");
  } catch (error) { renderError("operations", error); }
  finally { page.setAttribute("aria-busy", "false"); }
}

function wsCleanupValues(form, name) {
  return [...new Set(String(new FormData(form).get(name) || "").split(/[\s,]+/).map((item) => item.trim()).filter(Boolean))].sort();
}

function wsCleanupNotice(error, fallback) {
  if (!/cancelled/i.test(error?.message || "")) notice(fallback, true);
}

function wsCleanupBlockerText(type, count) {
  const total = Number(count) || 0;
  if (!total) return "";
  if (type === "invitations") {
    return `${total} selected invitation${total === 1 ? " is" : "s are"} not eligible for deletion. Revoke it or wait for it to become terminal, then create a new plan.`;
  }
  return `${total} selected record${total === 1 ? " is" : "s are"} not eligible for cleanup. Resolve the prerequisite and create a new plan.`;
}

async function renderCleanupWorkspace() {
  const fragment = document.createDocumentFragment();
  fragment.append(header("cleanup"));
  const warning = wsElement("section", "card danger-zone stack");
  warning.append(
    wsElement("h2", "", "Manual cleanup for explicitly selected data"),
    wsElement("p", "", "Only the owner runs this workspace. It does not schedule or automatically retain or delete data."),
    wsElement("p", "muted", "The server requires a verified backup, successful restore drill, recent reauthentication, drift detection, and exact confirmation before execution."),
  );
  const form = wsElement("form", "stack");
  form.append(
    wsField("Simulation session codes (comma or newline separated)", "sessionCodes", { multiline: true, rows: 4, placeholder: "ABC123\nDEF456" }),
    wsElement("h3", "", "Selected pre-production test data"),
    wsElement("p", "muted", "Enter only explicit invitation IDs copied from authorized Admin records. Do not enter names or email addresses. Invitations must already be revoked or otherwise terminal."),
    wsField("Invitation IDs (comma or newline separated)", "invitationIds", { multiline: true, rows: 3, placeholder: "Invitation IDs from authorized Admin records" }),
    wsElement("p", "muted", "This workspace does not delete user accounts. Suspend unwanted test users from Users to preserve audit history and prevent sign-in."),
  );
  const submit = button("Preview cleanup plan", "button-primary");
  submit.type = "submit";
  form.append(submit);
  warning.append(form);
  fragment.append(warning);
  page.replaceChildren(fragment);
  page.setAttribute("aria-busy", "false");
  let previewPending = false;
  form.addEventListener("submit", async (event) => {
    event.preventDefault();
    if (previewPending) return;
    const selector = {};
    const sessionCodes = wsCleanupValues(form, "sessionCodes");
    const invitationIds = wsCleanupValues(form, "invitationIds");
    if (sessionCodes.length) selector.sessionCodes = sessionCodes;
    if (invitationIds.length) selector.invitationIds = invitationIds;
    if (!Object.keys(selector).length) { notice("Enter at least one explicit session code or invitation ID.", true); return; }
    previewPending = true;
    submit.disabled = true;
    submit.setAttribute("aria-busy", "true");
    try {
      const response = await wsRecentMutation("/operations/cleanup-plans", { body: { selector } });
      const plan = response.plan;
      const rows = Object.entries(plan.previewCounts || {}).map(([type, count]) => ({ type: titleCase(type), count }));
      const total = rows.reduce((sum, row) => sum + (Number(row.count) || 0), 0);
      const panel = wsElement("section", "card stack cleanup-plan");
      panel.append(
        wsElement("h2", "", "Review server-generated cleanup plan"),
        wsElement("p", "muted", `Plan expires ${wsDate(plan.expiresAt)}. Any data drift invalidates it.`),
        wsElement("p", "", `Aggregate records selected for deletion: ${total}.`),
        wsTable([
          { label: "Record type", value: (row) => row.type },
          { label: "Count", value: (row) => row.count },
        ], rows),
      );
      const blockerCounts = plan && typeof plan.blockerCounts === "object" && plan.blockerCounts !== null ? plan.blockerCounts : {};
      const blockers = Object.entries(blockerCounts).filter(([, count]) => (Number(count) || 0) > 0);
      if (blockers.length) {
        const blockerSection = wsElement("section", "stack");
        blockerSection.append(wsElement("h3", "", "Safety blockers"));
        const list = wsElement("ul", "");
        for (const [type, count] of blockers) list.append(wsElement("li", "", wsCleanupBlockerText(type, count)));
        blockerSection.append(list, wsElement("p", "muted", "Blocker guidance is derived only from aggregate server counts and does not display selected record identities."));
        panel.append(blockerSection);
      }
      const confirmation = wsField("Type the exact confirmation text", "confirmation", { required: true, value: "", autocomplete: "off" });
      const execute = button("Execute bounded cleanup", "button-danger");
      execute.disabled = blockers.length > 0;
      if (blockers.length) execute.setAttribute("aria-disabled", "true");
      panel.append(wsElement("code", "confirmation-text", plan.confirmationText), confirmation, execute);
      let executePending = false;
      execute.addEventListener("click", async () => {
        if (executePending || execute.disabled) return;
        const typed = confirmation.querySelector("input").value;
        if (typed !== plan.confirmationText) { notice("Confirmation text does not match the server plan.", true); return; }
        executePending = true;
        execute.disabled = true;
        execute.textContent = "Executing bounded cleanup…";
        execute.setAttribute("aria-busy", "true");
        try {
          const result = await wsRecentMutation(`/operations/cleanup-plans/${encodeURIComponent(plan.id)}/execute`, {
            body: { planHash: plan.planHash, confirmation: typed },
          });
          const deleted = Object.values(result.deletedCounts || {}).reduce((sum, value) => sum + (Number(value) || 0), 0);
          await renderCleanupWorkspace();
          notice(`Cleanup completed. ${deleted} records deleted.`);
        } catch (error) { wsCleanupNotice(error, "Cleanup could not be completed. Refresh the plan and review the safety requirements before trying again."); }
        finally {
          executePending = false;
          execute.disabled = false;
          execute.removeAttribute("aria-busy");
          execute.textContent = "Execute bounded cleanup";
        }
      });
      warning.after(panel);
      notice("Review the server-generated plan, expiry, counts, and any safety blockers before executing.");
    } catch (error) { wsCleanupNotice(error, "Cleanup plan could not be created. Verify the selected records and required safety prerequisites, then try again."); }
    finally {
      previewPending = false;
      submit.disabled = false;
      submit.removeAttribute("aria-busy");
    }
  });
  status("Data retention and cleanup ready");
}

async function renderAccountWorkspace() {
  loading();
  notice("");
  try {
    const [current, mfaState] = await Promise.all([
      request("/auth/session"),
      request("/auth/mfa/status"),
    ]);
    if (current?.session) {
      state.session = current.session;
      state.csrf = current.session.csrfToken;
    }
    const fragment = document.createDocumentFragment();
    fragment.append(header("account"));
    const sessionCard = wsElement("section", "card stack");
    sessionCard.append(
      wsElement("h2", "", "Administrator session"),
      wsElement("p", "muted", "Authentication is held in a secure HTTP-only cookie and never stored in browser storage."),
      wsTable([
        { label: "Role", value: () => sessionRoleLabel(current.session.role) },
        { label: "Created", value: () => wsDate(current.session.createdAt) },
        { label: "Idle expiry", value: () => wsDate(current.session.idleExpiresAt) },
        { label: "Absolute expiry", value: () => wsDate(current.session.absoluteExpiresAt) },
      ], [current.session]),
    );
    const passwordCard = wsElement("section", "card stack");
    passwordCard.append(wsElement("h2", "", "Change password"), wsElement("p", "muted", "Changing the password revokes every existing Administrator session and creates one replacement session for this browser."));
    const change = button("Change Administrator password", "button-primary");
    change.addEventListener("click", async () => {
      const values = await wsDialog({
        title: "Change Administrator password",
        description: "Use at least 12 characters. A passphrase is recommended.",
        submitLabel: "Change password",
        fields: [
          { label: "Current password", name: "currentPassword", type: "password", autocomplete: "current-password", required: true, maxLength: 1024 },
          { label: "New password", name: "newPassword", type: "password", autocomplete: "new-password", required: true, minLength: 12, maxLength: 1024 },
          { label: "Confirm new password", name: "confirmation", type: "password", autocomplete: "new-password", required: true, minLength: 12, maxLength: 1024 },
        ],
      });
      if (!values) return;
      if (values.newPassword !== values.confirmation) { notice("New password confirmation does not match.", true); return; }
      change.disabled = true;
      try {
        await reauthenticate();
        const response = await request("/auth/password/change", { method: "POST", body: JSON.stringify({ currentPassword: values.currentPassword, newPassword: values.newPassword }) });
        setSession(response);
        await renderAccountWorkspace();
        notice("Administrator password changed and other sessions revoked.");
      } catch (error) { if (!/cancelled/i.test(error.message)) notice(error.message, true); }
      finally { change.disabled = false; }
    });
    passwordCard.append(change);
    const mfaCard = wsElement("section", "card stack");
    mfaCard.append(
      wsElement("h2", "", "Multi-factor authentication"),
      wsElement("p", "muted", mfaState.enabled
        ? "Administrator sign-in and sensitive reauthentication require an authenticator or one-time recovery code."
        : "Protect the Administrator account with the same authenticator and one-time recovery-code controls used by professor accounts."),
    );
    const mfaSummary = wsElement("div", "button-row");
    mfaSummary.append(badge(mfaState.enabled ? "Enabled" : "Not enabled"));
    if (mfaState.enabled) {
      mfaSummary.append(wsElement("span", "muted", `${mfaState.recoveryCodesRemaining} recovery codes remaining`));
    }
    mfaCard.append(mfaSummary);
    if (!mfaState.enabled) {
      const start = button("Set up Administrator MFA", "button-primary");
      start.addEventListener("click", async () => {
        const credentials = await wsDialog({
          title: "Confirm your Administrator password",
          description: "MFA setup creates a new authenticator secret. It is not enabled until you verify the first code.",
          submitLabel: "Continue",
          fields: [
            { label: "Current password", name: "password", type: "password", autocomplete: "current-password", required: true, maxLength: 1024 },
          ],
        });
        if (!credentials) return;
        start.disabled = true;
        try {
          const enrollment = await request("/auth/mfa/setup", { method: "POST", body: JSON.stringify({ password: credentials.password }) });
          const recoveryCodes = await wsConfirmMfaEnrollment(enrollment);
          if (!recoveryCodes) return;
          await wsShowRecoveryCodes(recoveryCodes);
          await renderAccountWorkspace();
          notice("Administrator MFA is enabled. Future sign-ins require a second factor.");
        } catch (error) { if (!/cancelled/i.test(error.message)) notice(error.message, true); }
        finally { start.disabled = false; }
      });
      mfaCard.append(start);
    } else {
      const controls = wsElement("div", "button-row");
      const regenerate = button("Replace recovery codes");
      regenerate.addEventListener("click", async () => {
        const values = await wsDialog({
          title: "Replace Administrator recovery codes",
          description: "Every existing recovery code will stop working. Use your password and a fresh authenticator or recovery code.",
          submitLabel: "Replace codes",
          fields: [
            { label: "Current password", name: "password", type: "password", autocomplete: "current-password", required: true, maxLength: 1024 },
            { label: "Fresh authenticator or recovery code", name: "code", autocomplete: "one-time-code", required: true, minLength: 6, maxLength: 64 },
          ],
        });
        if (!values) return;
        regenerate.disabled = true;
        try {
          const result = await request("/auth/mfa/recovery-codes", { method: "POST", body: JSON.stringify(values) });
          await wsShowRecoveryCodes(result.recoveryCodes, "Save your replacement recovery codes");
          await renderAccountWorkspace();
          notice("Administrator recovery codes replaced. Previous codes no longer work.");
        } catch (error) { if (!/cancelled/i.test(error.message)) notice(error.message, true); }
        finally { regenerate.disabled = false; }
      });
      const disable = button("Disable MFA", "button-danger");
      disable.addEventListener("click", async () => {
        const values = await wsDialog({
          title: "Disable Administrator MFA",
          description: "This reduces protection for the highest-privilege account. Confirm with your password and a fresh authenticator or recovery code.",
          submitLabel: "Disable MFA",
          danger: true,
          fields: [
            { label: "Current password", name: "password", type: "password", autocomplete: "current-password", required: true, maxLength: 1024 },
            { label: "Fresh authenticator or recovery code", name: "code", autocomplete: "one-time-code", required: true, minLength: 6, maxLength: 64 },
          ],
        });
        if (!values) return;
        disable.disabled = true;
        try {
          await request("/auth/mfa/disable", { method: "POST", body: JSON.stringify(values) });
          await renderAccountWorkspace();
          notice("Administrator MFA disabled.", true);
        } catch (error) { if (!/cancelled/i.test(error.message)) notice(error.message, true); }
        finally { disable.disabled = false; }
      });
      controls.append(regenerate, disable);
      mfaCard.append(controls);
    }
    fragment.append(sessionCard, mfaCard, passwordCard);
    page.replaceChildren(fragment);
    status("Account security loaded");
  } catch (error) { renderError("account", error); }
  finally { page.setAttribute("aria-busy", "false"); }
}
