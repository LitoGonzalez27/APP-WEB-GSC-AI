/**
 * AI Summary - Share
 * Acceso de solo lectura a una marca vía la infraestructura común de
 * colaboradores (/api/project-access, module_name='ai_summary').
 */

const ACCESS_API = '/api/project-access';

export function openShareModal() {
    const brand = this.getCurrentBrand();
    if (!brand?.is_owner) return;
    this.showShareError('');
    if (this.elements.shareEmailInput) this.elements.shareEmailInput.value = '';
    if (this.elements.shareModal) this.elements.shareModal.style.display = 'flex';
    this.loadShareData();
}

export function closeShareModal() {
    if (this.elements.shareModal) this.elements.shareModal.style.display = 'none';
}

export function showShareError(message) {
    const el = this.elements.shareError;
    if (!el) return;
    el.textContent = message || '';
    el.style.display = message ? 'block' : 'none';
}

export async function loadShareData() {
    const brand = this.getCurrentBrand();
    if (!brand) return;
    try {
        const data = await this.fetchJson(`${ACCESS_API}/projects/ai_summary/${brand.id}/members`);
        this.renderShareMembers(data.members || []);
        this.renderShareInvitations((data.invitations || []).filter(i => i.status === 'pending'));
    } catch (error) {
        console.error('❌ Error loading share data:', error);
        this.showShareError(error.message);
    }
}

export function renderShareMembers(members) {
    const list = this.elements.shareMembersList;
    if (!list) return;
    if (!members.length) {
        list.innerHTML = '<li class="share-empty">Only you have access.</li>';
        return;
    }
    list.innerHTML = members.map(m => `
        <li>
            <span class="share-identity">
                ${this.escapeHtml(m.name || m.email)}
                <span class="share-role">${m.is_owner ? 'owner' : this.escapeHtml(m.role || 'viewer')}</span>
            </span>
            ${m.is_owner ? '' : `
                <button type="button" class="share-remove-btn" data-member-id="${Number(m.user_id)}" title="Remove access">
                    <i class="fas fa-times"></i>
                </button>`}
        </li>
    `).join('');

    list.querySelectorAll('[data-member-id]').forEach(btn => {
        btn.addEventListener('click', () => this.removeShareMember(Number(btn.dataset.memberId)));
    });
}

export function renderShareInvitations(invitations) {
    const list = this.elements.shareInvitationsList;
    if (!list) return;
    if (!invitations.length) {
        list.innerHTML = '<li class="share-empty">No pending invitations.</li>';
        return;
    }
    list.innerHTML = invitations.map(inv => `
        <li>
            <span class="share-identity">
                ${this.escapeHtml(inv.invitee_email)}
                <span class="share-role">pending</span>
            </span>
            <button type="button" class="share-remove-btn" data-invitation-id="${Number(inv.id)}" title="Revoke invitation">
                <i class="fas fa-times"></i>
            </button>
        </li>
    `).join('');

    list.querySelectorAll('[data-invitation-id]').forEach(btn => {
        btn.addEventListener('click', () => this.revokeShareInvitation(Number(btn.dataset.invitationId)));
    });
}

export async function sendShareInvitation() {
    const brand = this.getCurrentBrand();
    const email = this.elements.shareEmailInput?.value.trim().toLowerCase();
    this.showShareError('');

    if (!brand || !email || !email.includes('@')) {
        this.showShareError('Enter a valid email address.');
        return;
    }

    try {
        this.elements.shareSendBtn.disabled = true;
        await this.fetchJson(`${ACCESS_API}/projects/ai_summary/${brand.id}/invitations`, {
            method: 'POST',
            body: JSON.stringify({ email, role: 'viewer' }),
        });
        this.elements.shareEmailInput.value = '';
        await this.loadShareData();
    } catch (error) {
        console.error('❌ Error sending invitation:', error);
        this.showShareError(error.message);
    } finally {
        this.elements.shareSendBtn.disabled = false;
    }
}

export async function revokeShareInvitation(invitationId) {
    try {
        await this.fetchJson(`${ACCESS_API}/invitations/${invitationId}`, { method: 'DELETE' });
        await this.loadShareData();
    } catch (error) {
        console.error('❌ Error revoking invitation:', error);
        this.showShareError(error.message);
    }
}

export async function removeShareMember(memberUserId) {
    const brand = this.getCurrentBrand();
    if (!brand) return;
    if (!confirm('Remove this person\'s access to the brand summary?')) return;
    try {
        await this.fetchJson(`${ACCESS_API}/projects/ai_summary/${brand.id}/members/${memberUserId}`, {
            method: 'DELETE',
        });
        await this.loadShareData();
    } catch (error) {
        console.error('❌ Error removing member:', error);
        this.showShareError(error.message);
    }
}
