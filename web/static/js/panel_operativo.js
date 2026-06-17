/**
 * panel_operativo.js
 * Lógica del Panel Operativo de Calidad.
 */

class PanelOperativo {
    constructor() {
        try {
            let registrosRaw = JSON.parse(document.getElementById('initial-data-registros').textContent);
            this.registros = typeof registrosRaw === 'string' ? JSON.parse(registrosRaw) : registrosRaw;
            if (!Array.isArray(this.registros)) this.registros = [];
            
            this.config = JSON.parse(document.getElementById('initial-data-config').textContent);
            this.lastId = this.config.last_id || 0;
            this.isSuperUser = this.config.is_superuser;
            this.orderAsc = true;
            this.pollingInterval = null;

            this.init();
        } catch (e) {
            console.error("Init Error:", e);
            document.querySelector('.table-wrapper table').innerHTML = `<tbody><tr><td style="color:var(--danger); padding: 20px; text-align:center;">Error al iniciar panel: ${e.message}</td></tr></tbody>`;
        }
    }

    init() {
        this.cacheDOM();
        this.bindEvents();
        this.renderTabla();
        this.startPolling();
    }

    cacheDOM() {
        this.table = document.querySelector('.table-wrapper table');
        this.searchInput = document.getElementById('search-input');
        this.selectAllCheckbox = document.getElementById('selectAll');
        this.toast = document.getElementById('toast');
        this.editModal = document.getElementById('edit-modal');
        this.excelForm = document.getElementById('form-excel');
        this.excelDataInput = document.getElementById('registros_data_input');
        
        this.floatingActionBar = document.getElementById('floating-action-bar');
        this.selectionCountText = document.getElementById('selection-count-text');

        // Edit form fields
        this.editId = document.getElementById('edit-id');
        this.editCant = document.getElementById('edit-cant');
        this.editLinea = document.getElementById('edit-linea');
        this.editResp = document.getElementById('edit-resp');
        this.editDesc = document.getElementById('edit-desc');
    }

    bindEvents() {
        // Search
        this.searchInput.addEventListener('input', () => this.filtrarTabla());

        // Keyboard shortcut for search
        document.addEventListener('keydown', (e) => {
            if (e.key === '/' && document.activeElement !== this.searchInput && document.activeElement.tagName !== 'INPUT') {
                e.preventDefault();
                this.searchInput.focus();
            }
        });

        // Table actions delegation
        this.table.addEventListener('click', (e) => {
            const target = e.target;
            
            // Toggle Group
            const groupHeader = target.closest('.group-header');
            if (groupHeader) {
                const btnSelectUser = target.closest('.btn-select-user');
                if (btnSelectUser) {
                    this.toggleSelectUser(btnSelectUser.dataset.user);
                    return;
                }
                this.toggleGrupo(groupHeader.dataset.groupId);
                return;
            }

            // Action buttons
            const editBtn = target.closest('.btn-edit');
            if (editBtn) {
                this.editarRegistro(parseInt(editBtn.dataset.id));
                return;
            }
            const deleteBtn = target.closest('.btn-delete');
            if (deleteBtn) {
                this.eliminarRegistro(parseInt(deleteBtn.dataset.id));
                return;
            }

            // Row click for selection
            const tr = target.closest('tr');
            if (tr && tr.dataset.index !== undefined && !target.closest('th')) {
                // Evitar selección de texto con doble click rápido
                if (e.detail > 1) {
                    window.getSelection().removeAllRanges();
                }
                // Si hizo clic en checkbox directamente, actualizar estado
                if (target.type === 'checkbox') {
                    const idx = parseInt(tr.dataset.index);
                    this.registros[idx]._selected = target.checked;
                    tr.classList.toggle('selected', target.checked);
                    this.updateSelectionState();
                } else {
                    this.toggleSelect(parseInt(tr.dataset.index));
                }
                return;
            }

            // Column Sort
            const th = target.closest('th[data-sort]');
            if (th) {
                this.ordenar(th.dataset.sort);
            }
        });

        this.selectAllCheckbox.addEventListener('change', () => this.toggleSelectAll());

        // Buttons
        document.getElementById('btn-agrupar').addEventListener('click', () => this.agruparSeleccionados());
        document.getElementById('btn-excel').addEventListener('click', () => this.enviarExcel());
        
        // Modal buttons
        document.getElementById('btn-modal-cancel').addEventListener('click', () => this.cerrarModal());
        document.getElementById('btn-modal-save').addEventListener('click', () => this.guardarEdicion());
    }

    // --- RENDERIZADO ---

    renderTabla() {
        // Eliminar tbodys anteriores
        this.table.querySelectorAll('tbody').forEach(tb => tb.remove());
        
        if (this.registros.length === 0) {
            this.renderEmptyState('No hay registros para mostrar.');
            return;
        }

        const grupos = {};
        let hasVisibleRows = false;

        this.registros.forEach((r, index) => {
            r._originalIndex = index;
            if (r._hidden) return;
            hasVisibleRows = true;
            if (!grupos[r.user_id]) grupos[r.user_id] = [];
            grupos[r.user_id].push(r);
        });

        if (!hasVisibleRows) {
            this.renderEmptyState('Ningún registro coincide con la búsqueda.');
            return;
        }

        Object.keys(grupos).forEach(userId => {
            this.renderGrupo(userId, grupos[userId]);
        });

        this.initSortable();
        this.updateSelectionState();

        // Auto expand if search
        const term = this.searchInput.value.trim();
        if (term !== '') {
            document.querySelectorAll('.sortable-tbody').forEach(tb => {
                tb.style.display = '';
                const icon = document.getElementById(`icon-${tb.id}`);
                if (icon) icon.textContent = '▼';
            });
        }
    }

    renderEmptyState(msg) {
        const tbody = document.createElement('tbody');
        tbody.innerHTML = `<tr><td colspan="10" style="text-align:center; color:var(--text-muted); padding:30px;">${msg}</td></tr>`;
        this.table.appendChild(tbody);
    }

    renderGrupo(userId, g) {
        const colspan = this.isSuperUser ? 10 : 9;
        const headerTbody = document.createElement('tbody');
        headerTbody.innerHTML = `
            <tr class="group-header" data-group-id="group-${userId}" style="background: var(--surface2); cursor: pointer; transition: background 0.2s; user-select: none;" role="button" aria-expanded="false">
                <td style="vertical-align: middle;">
                    <span class="drag-handle" style="visibility: hidden;">⠿</span>
                    <input type="checkbox" class="group-check btn-select-user" data-user="${userId}" aria-label="Seleccionar grupo completo" style="cursor: pointer; transform: scale(1.1); margin: 0;">
                </td>
                <td colspan="${colspan - 1}">
                    <div style="display:flex; align-items:center;">
                        <span id="icon-group-${userId}" style="display:inline-block; width:24px; color: var(--text-muted); transition: transform 0.2s; font-size: 0.9rem;">▶</span>
                        <span style="font-weight: 500; margin-right: 8px; color: var(--text);">Usuario</span>
                        <span class="badge-user" style="font-size: 0.9rem; padding: 4px 8px;">${userId}</span>
                        <span class="badge" style="margin-left: 12px; background: rgba(255,255,255,0.05); color: var(--text-muted); border: 1px solid var(--border); font-size: 0.8rem;">
                            ${g.length} registro${g.length !== 1 ? 's' : ''}
                        </span>
                    </div>
                </td>
            </tr>
        `;
        this.table.appendChild(headerTbody);

        const rowsTbody = document.createElement('tbody');
        rowsTbody.id = `group-${userId}`;
        rowsTbody.className = 'sortable-tbody';
        rowsTbody.style.display = 'none';

        g.forEach(r => {
            const tr = document.createElement('tr');
            tr.id = `row-${r.id}`;
            tr.dataset.index = r._originalIndex;
            if (r._agrupado) tr.classList.add('agrupada');
            if (r._selected) tr.classList.add('selected');
            if (r._disabled) tr.classList.add('disabled-row');
            if (r._isNew) tr.classList.add('new-row');

            const dateObj = r.fecha_registro ? new Date(r.fecha_registro) : new Date();
            const dateStr = dateObj.toLocaleTimeString([], {hour: '2-digit', minute:'2-digit'});
            
            const fotosStr = r.fotos_nums && r.fotos_nums.length > 0 
                ? `${r.fotos_nums.length} fotos` 
                : (r.fotos_str || '-');

            tr.innerHTML = `
                <td>
                    <span class="drag-handle" aria-label="Arrastrar para reordenar">⠿</span>
                    <input type="checkbox" class="row-check" ${r._selected ? 'checked' : ''} ${r._disabled ? 'disabled' : ''} aria-label="Seleccionar registro">
                </td>
                <td style="font-size:0.8rem; color:var(--text-muted);">${dateStr}</td>
                <td style="font-weight:500;">${r.modelo}</td>
                <td><span class="badge badge-purple">${r.linea}</span></td>
                <td style="font-size:0.9rem;">${r.descripcion}</td>
                <td>${r.responsable}</td>
                <td><code style="color:var(--text-muted); font-size:0.85rem; background:none; padding:0;">${fotosStr}</code></td>
                <td style="font-weight:bold;">${r.cantidad || 1}</td>
                <td><span class="badge-user">${r.user_id}</span></td>
                ${this.isSuperUser ? `
                <td style="text-align:center;" class="row-actions">
                    <button class="btn btn-ghost btn-edit" data-id="${r.id}" title="Editar" aria-label="Editar registro">✏️</button>
                    <button class="btn btn-ghost btn-delete" data-id="${r.id}" title="Eliminar" aria-label="Eliminar registro" style="color:var(--danger);">🗑️</button>
                </td>` : ''}
            `;
            rowsTbody.appendChild(tr);
        });
        this.table.appendChild(rowsTbody);
    }

    // --- ACCIONES ---

    toggleGrupo(groupId) {
        const tbody = document.getElementById(groupId);
        const header = document.querySelector(`[data-group-id="${groupId}"]`);
        const icon = document.getElementById(`icon-${groupId}`);
        const isHidden = tbody.style.display === 'none';

        tbody.style.display = isHidden ? '' : 'none';
        icon.style.transform = isHidden ? 'rotate(90deg)' : 'rotate(0deg)';
        header.setAttribute('aria-expanded', isHidden);
    }

    toggleSelectAll() {
        const checked = this.selectAllCheckbox.checked;
        this.registros.forEach(r => { if (!r._hidden) r._selected = checked; });
        this.updateSelectionState();
        
        // Actualizar UI sin re-renderizar todo el DOM
        this.registros.forEach(r => {
            if (!r._hidden) {
                const tr = document.querySelector(`tr[data-index="${r._originalIndex}"]`);
                if (tr) {
                    tr.classList.toggle('selected', checked);
                    const cb = tr.querySelector('.row-check');
                    if (cb) cb.checked = checked;
                }
            }
        });
    }

    toggleSelectUser(userId) {
        const groupRegs = this.registros.filter(r => String(r.user_id) === String(userId) && !r._hidden);
        const allSelected = groupRegs.length > 0 && groupRegs.every(r => r._selected);
        const newState = !allSelected;
        
        groupRegs.forEach(r => r._selected = newState);
        
        groupRegs.forEach(r => {
            const tr = document.querySelector(`tr[data-index="${r._originalIndex}"]`);
            if (tr) {
                tr.classList.toggle('selected', newState);
                const cb = tr.querySelector('.row-check');
                if (cb) cb.checked = newState;
            }
        });
        this.updateSelectionState();
    }

    toggleSelect(index) {
        this.registros[index]._selected = !this.registros[index]._selected;
        
        const tr = document.querySelector(`tr[data-index="${index}"]`);
        if (tr) {
            tr.classList.toggle('selected', this.registros[index]._selected);
            const cb = tr.querySelector('.row-check');
            if (cb) cb.checked = this.registros[index]._selected;
        }
        this.updateSelectionState();
    }

    updateSelectionState() {
        const visibleRegs = this.registros.filter(r => !r._hidden);
        const selected = this.registros.filter(r => r._selected && !r._hidden);
        const count = selected.length;
        const btnAgrupar = document.getElementById('btn-agrupar');
        
        if (visibleRegs.length > 0 && count === visibleRegs.length) {
            this.selectAllCheckbox.checked = true;
            this.selectAllCheckbox.indeterminate = false;
        } else if (count > 0) {
            this.selectAllCheckbox.checked = false;
            this.selectAllCheckbox.indeterminate = true;
        } else {
            this.selectAllCheckbox.checked = false;
            this.selectAllCheckbox.indeterminate = false;
        }

        if (count > 0) {
            this.selectionCountText.textContent = `${count} seleccionado${count !== 1 ? 's' : ''}`;
            this.floatingActionBar.classList.add('visible');
            this.floatingActionBar.setAttribute('aria-hidden', 'false');
            
            // Validate compatibility for "Agrupar" button
            let compatible = true;
            let reason = "";
            if (count > 1) {
                const ref = selected[0];
                for (let i = 1; i < count; i++) {
                    const r = selected[i];
                    
                    if (String(r.user_id) !== String(ref.user_id)) {
                        compatible = false; reason = "Distinto usuario"; break;
                    }
                    if (String(r.modelo || '').trim().toLowerCase() !== String(ref.modelo || '').trim().toLowerCase()) {
                        compatible = false; reason = "Distinto modelo"; break;
                    }
                    if (String(r.descripcion || '').trim().toLowerCase() !== String(ref.descripcion || '').trim().toLowerCase()) {
                        compatible = false; reason = "Distinta descripción"; break;
                    }
                    if (String(r.responsable || '').trim().toLowerCase() !== String(ref.responsable || '').trim().toLowerCase()) {
                        compatible = false; reason = "Distinto responsable"; break;
                    }
                    
                    if (r.fecha_registro && ref.fecha_registro) {
                        const t1 = new Date(ref.fecha_registro).getTime();
                        const t2 = new Date(r.fecha_registro).getTime();
                        if (Math.abs(t1 - t2) > 2 * 60 * 60 * 1000) {
                            compatible = false; reason = "Diferencia > 2 horas"; break;
                        }
                    }
                }
            } else {
                compatible = false;
                reason = "Selecciona al menos 2";
            }
            
            btnAgrupar.disabled = !compatible;
            if (!compatible) {
                btnAgrupar.title = `Incompatible: ${reason}`;
                btnAgrupar.style.opacity = '0.5';
                btnAgrupar.style.cursor = 'not-allowed';
            } else {
                btnAgrupar.title = "";
                btnAgrupar.style.opacity = '1';
                btnAgrupar.style.cursor = 'pointer';
            }

        } else {
            this.floatingActionBar.classList.remove('visible');
            this.floatingActionBar.setAttribute('aria-hidden', 'true');
        }

        // Sync group checkboxes
        const groups = [...new Set(visibleRegs.map(r => r.user_id))];
        groups.forEach(userId => {
            const groupRegs = visibleRegs.filter(r => r.user_id === userId);
            const groupSelected = groupRegs.filter(r => r._selected).length;
            const groupCheckbox = document.querySelector(`.group-check[data-user="${userId}"]`);
            if (groupCheckbox) {
                if (groupSelected === 0) {
                    groupCheckbox.checked = false;
                    groupCheckbox.indeterminate = false;
                } else if (groupSelected === groupRegs.length) {
                    groupCheckbox.checked = true;
                    groupCheckbox.indeterminate = false;
                } else {
                    groupCheckbox.checked = false;
                    groupCheckbox.indeterminate = true;
                }
            }
        });
    }

    filtrarTabla() {
        const term = this.searchInput.value.toLowerCase();
        this.registros.forEach((r, idx) => {
            const match = `${r.modelo} ${r.linea} ${r.descripcion} ${r.responsable} ${r.user_id}`.toLowerCase().includes(term);
            r._hidden = !match;
            const tr = document.querySelector(`tr[data-index="${idx}"]`);
            if (tr) tr.classList.toggle('hidden', !match);
        });
    }

    ordenar(campo) {
        this.registros.sort((a, b) => {
            let valA = a[campo] || '';
            let valB = b[campo] || '';
            if (campo === 'fecha') {
                valA = a.fecha_registro ? new Date(a.fecha_registro).getTime() : 0;
                valB = b.fecha_registro ? new Date(b.fecha_registro).getTime() : 0;
            }
            if (valA < valB) return this.orderAsc ? -1 : 1;
            if (valA > valB) return this.orderAsc ? 1 : -1;
            return 0;
        });
        this.orderAsc = !this.orderAsc;
        this.renderTabla();
    }

    async agruparSeleccionados() {
        const seleccionados = this.registros.filter(r => r._selected && !r._hidden);
        if (seleccionados.length < 2) {
            this.mostrarToast("Selecciona al menos 2 registros para agrupar.");
            return;
        }

        const ref = seleccionados[0];
        
        // Reglas de negocio para agrupación
        for (let i = 1; i < seleccionados.length; i++) {
            const r = seleccionados[i];
            if (String(r.user_id) !== String(ref.user_id)) {
                this.mostrarToast("❌ No se pueden agrupar fotos de distintos usuarios.");
                return;
            }
            if (String(r.modelo || '').trim().toLowerCase() !== String(ref.modelo || '').trim().toLowerCase() || 
                String(r.descripcion || '').trim().toLowerCase() !== String(ref.descripcion || '').trim().toLowerCase() || 
                String(r.responsable || '').trim().toLowerCase() !== String(ref.responsable || '').trim().toLowerCase()) {
                this.mostrarToast("❌ Modelo, descripción o responsable no coinciden.");
                return;
            }
            
            // Diferencia horaria máxima 2h
            if (r.fecha_registro && ref.fecha_registro) {
                const t1 = new Date(ref.fecha_registro).getTime();
                const t2 = new Date(r.fecha_registro).getTime();
                if (Math.abs(t1 - t2) > 2 * 60 * 60 * 1000) {
                    this.mostrarToast("❌ Los registros superan las 2 horas de diferencia.");
                    return;
                }
            }
        }

        const fotosSet = new Set();
        let totalCantidad = 0;
        seleccionados.forEach(r => {
            (r.fotos_nums || []).forEach(n => fotosSet.add(n));
            totalCantidad += (r.cantidad || 1);
        });

        const superRegistro = { ...ref };
        superRegistro.fotos_nums = Array.from(fotosSet).sort((a, b) => a - b);
        superRegistro.cantidad = totalCantidad;
        superRegistro.fotos_str = `(${superRegistro.fotos_nums[0]}-${superRegistro.fotos_nums[superRegistro.fotos_nums.length-1]})`;
        superRegistro._agrupado = true;
        superRegistro._selected = true;

        this.registros = this.registros.filter(r => !seleccionados.includes(r));
        this.registros.unshift(superRegistro);
        
        this.selectAllCheckbox.checked = false;
        this.renderTabla();
        this.mostrarToast("✅ Registros agrupados correctamente.", "var(--success)");
    }

    // --- API & PERSISTENCIA ---

    getCsrfToken() {
        // Primero intentar desde el meta tag
        const meta = document.querySelector('meta[name="csrf-token"]');
        if (meta) return meta.content;
        // Fallback a cookie
        const name = 'csrftoken';
        let cookieValue = null;
        if (document.cookie && document.cookie !== '') {
            const cookies = document.cookie.split(';');
            for (let i = 0; i < cookies.length; i++) {
                const cookie = cookies[i].trim();
                if (cookie.substring(0, name.length + 1) === (name + '=')) {
                    cookieValue = decodeURIComponent(cookie.substring(name.length + 1));
                    break;
                }
            }
        }
        return cookieValue;
    }

    async eliminarRegistro(id) {
        if (!confirm("¿Seguro que deseas eliminar este registro permanentemente?")) return;
        try {
            const res = await fetch(`/api/registro/${id}/delete/`, {
                method: 'POST',
                headers: { 'X-CSRFToken': this.getCsrfToken() }
            });
            if (res.ok) {
                this.registros = this.registros.filter(r => r.id !== id);
                this.renderTabla();
                this.mostrarToast("🗑️ Registro eliminado", "var(--success)");
            } else {
                this.mostrarToast("Error: No tienes permisos o el registro no existe.");
            }
        } catch(e) { 
            console.error(e);
            this.mostrarToast("Error de conexión al eliminar.");
        }
    }

    editarRegistro(id) {
        const reg = this.registros.find(r => r.id === id);
        if (!reg) return;
        
        this.editId.value = id;
        this.editCant.value = reg.cantidad || 1;
        this.editLinea.value = reg.linea || '';
        this.editResp.value = reg.responsable || '';
        this.editDesc.value = reg.descripcion || '';
        
        this.editModal.style.display = 'flex';
    }

    cerrarModal() {
        this.editModal.style.display = 'none';
    }

    async guardarEdicion() {
        const id = parseInt(this.editId.value);
        const payload = {
            cantidad: parseInt(this.editCant.value),
            linea: this.editLinea.value.trim(),
            responsable: this.editResp.value.trim(),
            descripcion: this.editDesc.value.trim()
        };
        
        if (!payload.cantidad || !payload.responsable || !payload.descripcion || !payload.linea) {
            this.mostrarToast("Todos los campos son obligatorios.");
            return;
        }
        
        try {
            const res = await fetch(`/api/registro/${id}/edit/`, {
                method: 'POST',
                headers: {
                    'Content-Type': 'application/json',
                    'X-CSRFToken': this.getCsrfToken()
                },
                body: JSON.stringify(payload)
            });
            if (res.ok) {
                const reg = this.registros.find(r => r.id === id);
                Object.assign(reg, payload);
                this.renderTabla();
                this.cerrarModal();
                this.mostrarToast("✏️ Registro actualizado", "var(--success)");
            } else {
                this.mostrarToast("Error al editar registro.");
            }
        } catch(e) { 
            console.error(e);
            this.mostrarToast("Error de red al guardar.");
        }
    }

    enviarExcel() {
        const seleccionados = this.registros.filter(r => r._selected && !r._hidden);
        if (seleccionados.length === 0) {
            this.mostrarToast("Selecciona al menos 1 registro para enviar.");
            return;
        }

        if (!confirm(`¿Estás seguro de procesar ${seleccionados.length} registros a Excel?`)) return;

        const btnExcel = document.getElementById('btn-excel');
        const textOriginal = btnExcel.innerHTML;
        btnExcel.innerHTML = '<span class="spinner" style="width:14px;height:14px;border-width:2px;margin-right:8px;vertical-align:middle;"></span> Procesando...';
        btnExcel.disabled = true;
        this.mostrarToast("⏳ Preparando Excel... Esto puede tardar si hay muchas fotos.", "var(--accent)");

        // Limpiar y ordenar fotos antes de enviar
        seleccionados.forEach(r => {
            if (r.fotos_nums && Array.isArray(r.fotos_nums)) {
                r.fotos_nums = [...new Set(r.fotos_nums)].sort((a,b) => a - b);
            }
        });

        this.excelDataInput.value = JSON.stringify(seleccionados);
        this.excelForm.submit();
        
        // Restaurar botón después de 5s por si el usuario usa el botón "Atrás" del navegador
        setTimeout(() => {
            btnExcel.innerHTML = textOriginal;
            btnExcel.disabled = false;
        }, 5000);
    }

    // --- POLLING & NOTIFICACIONES ---

    startPolling() {
        if (this.pollingInterval) clearInterval(this.pollingInterval);
        this.pollingInterval = setInterval(() => this.checkUpdates(), 10000);
    }

    async checkUpdates() {
        try {
            const res = await fetch(`/api/check_updates/?last_id=${this.lastId}`);
            if (res.status === 304) return; 
            
            const data = await res.json();
            if (data.has_updates && data.nuevos_count > 0) {
                this.fetchNuevos(); // Auto inject silently
            }
        } catch(e) { console.warn("Polling falló:", e); }
    }

    async fetchNuevos() {
        try {
            const res = await fetch(`/api/get_nuevos/?last_id=${this.lastId}`);
            const data = await res.json();
            if (data.registros && data.registros.length > 0) {
                // Evitar duplicados por si acaso
                const existingIds = new Set(this.registros.map(r => r.id));
                const nuevos = data.registros.filter(r => !existingIds.has(r.id));
                
                nuevos.forEach(n => n._isNew = true);
                
                this.registros = [...nuevos, ...this.registros];
                this.lastId = Math.max(this.lastId, ...nuevos.map(r => r.id));
                this.renderTabla();
                
                // Cleanup animation class after it plays
                setTimeout(() => {
                    this.registros.forEach(r => r._isNew = false);
                }, 3000);
            }
        } catch(e) { console.error("Error trayendo nuevos:", e); }
    }

    mostrarToast(msg, bg = "var(--danger)") {
        this.toast.textContent = msg;
        this.toast.style.background = bg;
        this.toast.style.display = 'block';
        this.toast.setAttribute('role', bg === 'var(--danger)' ? 'alert' : 'status');
        
        if (this.toastTimeout) clearTimeout(this.toastTimeout);
        this.toastTimeout = setTimeout(() => { 
            this.toast.style.display = 'none'; 
        }, 4000);
    }

    // --- SORTABLE ---

    initSortable() {
        if (this.sortableInstances) {
            this.sortableInstances.forEach(s => s.destroy());
        }
        this.sortableInstances = [];

        document.querySelectorAll('.sortable-tbody').forEach(tbody => {
            const s = new Sortable(tbody, {
                handle: '.drag-handle',
                animation: 150,
                ghostClass: 'sortable-ghost',
                onEnd: () => {
                    if (this.searchInput.value.trim() !== '') {
                        this.mostrarToast("No se puede reordenar con búsqueda activa.");
                        this.renderTabla();
                        return;
                    }

                    // Reconstruir orden global
                    const nuevoOrden = [];
                    document.querySelectorAll('.sortable-tbody tr').forEach((tr) => {
                        const index = parseInt(tr.dataset.index);
                        nuevoOrden.push(this.registros[index]);
                    });
                    
                    this.registros = nuevoOrden;
                    this.renderTabla();
                    
                    // Sugerencia: Aquí se podría enviar el nuevo orden al servidor:
                    // this.saveOrderToServer();
                }
            });
            this.sortableInstances.push(s);
        });
    }
}

// Iniciar aplicación
document.addEventListener('DOMContentLoaded', () => {
    window.app = new PanelOperativo();
});
