from datetime import timedelta

from odoo import api, fields, models
from odoo.exceptions import UserError, ValidationError
from odoo.tools.translate import _


class OfficeAssetLoan(models.Model):
    _name = 'office.asset.loan'
    _description = 'Office Asset Loan'
    _order = 'loan_date desc, id desc'

    name = fields.Char(
        string='Loan Reference',
        required=True,
        copy=False,
        readonly=True,
        default='New',
    )
    asset_id = fields.Many2one(
        'office.asset',
        string='Asset',
        required=True,
        ondelete='restrict',
    )
    borrower_id = fields.Many2one(
        'res.users',
        string='Borrower',
        required=True,
        default=lambda self: self.env.user,
    )
    loan_date = fields.Date(
        string='Loan Date',
        required=True,
        default=fields.Date.context_today,
    )
    due_date = fields.Date(string='Due Date', required=True)
    return_date = fields.Date(string='Return Date', readonly=True)
    purpose = fields.Char(string='Purpose')
    state = fields.Selection([
        ('draft', 'Draft'),
        ('borrowed', 'Borrowed'),
        ('returned', 'Returned'),
        ('cancelled', 'Cancelled'),
    ], string='Status', default='draft', copy=False, index=True)

    # Compute fields
    duration_days = fields.Integer(
        string='Duration (Days)',
        compute='_compute_duration_days',
    )
    is_overdue = fields.Boolean(
        string='Overdue',
        compute='_compute_is_overdue',
        search='_search_is_overdue',
    )

    # SQL constraint (Odoo 19: models.Constraint di dalam _constraints)
    _constraints = [
        models.Constraint(
            'CHECK(due_date >= loan_date)',
            'Tanggal jatuh tempo tidak boleh lebih awal dari tanggal pinjam.',
        ),
    ]

    @api.depends('loan_date', 'due_date')
    def _compute_duration_days(self):
        for record in self:
            if record.loan_date and record.due_date:
                record.duration_days = (record.due_date - record.loan_date).days
            else:
                record.duration_days = 0

    @api.depends('state', 'due_date')
    def _compute_is_overdue(self):
        today = fields.Date.context_today(self)
        for record in self:
            record.is_overdue = bool(
                record.state == 'borrowed'
                and record.due_date
                and record.due_date < today
            )

    def _search_is_overdue(self, operator, value):
        # Implementasi search agar field computed (non-stored) bisa difilter
        today = fields.Date.context_today(self)
        is_overdue = (operator == '=' and value) or (operator == '!=' and not value)
        if is_overdue:
            return [('state', '=', 'borrowed'), ('due_date', '<', today)]
        return ['|', ('state', '!=', 'borrowed'), ('due_date', '>=', today)]

    # BR-2: Validasi due_date tidak boleh lebih awal dari loan_date
    @api.constrains('loan_date', 'due_date')
    def _check_dates(self):
        for record in self:
            if (
                record.loan_date
                and record.due_date
                and record.due_date < record.loan_date
            ):
                raise ValidationError(
                    _('Tanggal Due Date tidak boleh lebih awal dari Tanggal Loan Date!')
                )

    @api.model_create_multi
    def create(self, vals_list):
        # Generate nomor referensi dari sequence LOAN/000X
        for vals in vals_list:
            if not vals.get('name') or vals['name'] == 'New':
                vals['name'] = (
                    self.env['ir.sequence'].next_by_code('office.asset.loan')
                    or 'New'
                )
        return super().create(vals_list)

    @api.onchange('loan_date')
    def _onchange_loan_date(self):
        # due_date otomatis terisi 7 hari setelah loan_date
        if self.loan_date:
            self.due_date = self.loan_date + timedelta(days=7)

    def action_borrow(self):
        for record in self:
            if record.state != 'draft':
                raise UserError(_('Hanya peminjaman berstatus Draft yang bisa dipinjam.'))
            # BR-4: aset rusak tidak boleh dipinjam
            if record.asset_id.condition == 'damaged':
                raise UserError(
                    _('Peminjaman ditolak karena kondisi aset "%s" sedang Damaged (rusak).')
                    % record.asset_id.name
                )
            if record.asset_id and not record.asset_id.is_available:
                raise UserError(
                    _('Aset "%s" sedang dipinjam dan belum dikembalikan.') % record.asset_id.name
                )
        self.write({'state': 'borrowed'})

    def action_return(self):
        today = fields.Date.context_today(self)
        for record in self:
            if record.state != 'borrowed':
                raise UserError(_('Hanya peminjaman berstatus Borrowed yang bisa dikembalikan.'))
        self.write({'state': 'returned', 'return_date': today})

    def action_cancel(self):
        for record in self:
            if record.state not in ('draft', 'borrowed'):
                raise UserError(_('Peminjaman yang sudah Returned atau Cancelled tidak bisa dibatalkan.'))
        self.write({'state': 'cancelled'})

    def unlink(self):
        # Tolak hapus jika peminjaman berstatus borrowed atau returned
        for record in self:
            if record.state in ('borrowed', 'returned'):
                raise UserError(
                    _('Peminjaman %s tidak boleh dihapus karena berstatus %s.')
                    % (record.name, record.state)
                )
        return super().unlink()
