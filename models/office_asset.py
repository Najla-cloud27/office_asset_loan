from datetime import timedelta
from odoo import models, fields, api
from odoo.exceptions import ValidationError, UserError


class OfficeAsset(models.Model):
    _name = 'office.asset'
    _description = 'Office Asset'

    # BR-1: Unique Asset Code (Sintaks Odoo 19)
    _constraints = [
        models.Constraint('UNIQUE(code)', 'Kode aset tidak boleh sama dengan aset lain!'),
    ]

    name = fields.Char(string='Asset Name', required=True)
    code = fields.Char(string='Asset Code', required=True)
    category = fields.Selection([
        ('electronics', 'Electronics'),
        ('furniture', 'Furniture'),
        ('vehicle', 'Vehicle'),
        ('other', 'Other'),
    ], string='Category', default='electronics')
    condition = fields.Selection([
        ('good', 'Good'),
        ('fair', 'Fair'),
        ('damaged', 'Damaged'),
    ], string='Condition', default='good')
    purchase_date = fields.Date(string='Purchase Date')
    note = fields.Text(string='Note')
    active = fields.Boolean(string='Active', default=True)

    loan_ids = fields.One2many('office.asset.loan', 'asset_id', string='Loans')
    loan_count = fields.Integer(string='Jumlah Peminjaman', compute='_compute_loan_count')
    is_available = fields.Boolean(string='Available', compute='_compute_is_available', store=False)

    @api.depends('loan_ids')
    def _compute_loan_count(self):
        for record in self:
            record.loan_count = len(record.loan_ids)

    @api.depends('loan_ids.state')
    def _compute_is_available(self):
        for record in self:
            borrowed_loans = record.loan_ids.filtered(lambda l: l.state == 'borrowed')
            record.is_available = not bool(borrowed_loans)


class OfficeAssetLoan(models.Model):
    _name = 'office.asset.loan'
    _description = 'Office Asset Loan'

    name = fields.Char(string='Loan Reference', required=True, copy=False, readonly=True, default='New')
    asset_id = fields.Many2one('office.asset', string='Asset', required=True, ondelete='restrict')
    borrower_id = fields.Many2one('res.users', string='Borrower', default=lambda self: self.env.user, required=True)
    loan_date = fields.Date(string='Loan Date', default=fields.Date.context_today, required=True)
    due_date = fields.Date(string='Due Date', required=True)
    return_date = fields.Date(string='Return Date', readonly=True)
    purpose = fields.Char(string='Purpose')
    
    state = fields.Selection([
        ('draft', 'Draft'),
        ('borrowed', 'Borrowed'),
        ('returned', 'Returned'),
        ('cancelled', 'Cancelled'),
    ], string='State', default='draft', required=True)

    duration_days = fields.Integer(string='Duration (Days)', compute='_compute_duration_days')
    is_overdue = fields.Boolean(string='Overdue', compute='_compute_is_overdue')

    @api.depends('loan_date', 'due_date')
    def _compute_duration_days(self):
        for record in self:
            if record.loan_date and record.due_date:
                delta = record.due_date - record.loan_date
                record.duration_days = delta.days
            else:
                record.duration_days = 0

    @api.depends('due_date', 'state')
    def _compute_is_overdue(self):
        today = fields.Date.context_today(self)
        for record in self:
            if record.state == 'borrowed' and record.due_date and record.due_date < today:
                record.is_overdue = True
            else:
                record.is_overdue = False

    # BR-2: Validasi due_date tidak boleh lebih awal dari loan_date
    @api.constrains('loan_date', 'due_date')
    def _check_dates(self):
        for record in self:
            if record.loan_date and record.due_date and record.due_date < record.loan_date:
                raise ValidationError('Tanggal Due Date tidak boleh lebih awal dari Tanggal Loan Date!')

    # BR-8: Auto-fill due_date = loan_date + 7 hari saat loan_date diubah
    @api.onchange('loan_date')
    def _onchange_loan_date(self):
        if self.loan_date:
            if not self.due_date or self.due_date < self.loan_date:
                self.due_date = self.loan_date + timedelta(days=7)

    # BR-3: Override create() dengan @api.model_create_multi (Odoo 19 Standard)
    @api.model_create_multi
    def create(self, vals_list):
        for vals in vals_list:
            if vals.get('name', 'New') == 'New':
                vals['name'] = self.env['ir.sequence'].next_by_code('office.asset.loan') or 'New'
        return super(OfficeAssetLoan, self).create(vals_list)

    # BR-7: Tidak boleh menghapus transaksi Borrowed/Returned
    @api.ondelete(at_uninstall=False)
    def _unlink_except_borrowed_or_returned(self):
        for record in self:
            if record.state in ('borrowed', 'returned'):
                raise UserError('Peminjaman yang berstatus Borrowed atau Returned tidak boleh dihapus!')

    # BR-4: Action Borrow (Cek Availability & Damaged)
    def action_borrow(self):
        for record in self:
            if record.asset_id.condition == 'damaged':
                raise UserError('Peminjaman ditolak karena kondisi aset dalam keadaan Rusak (Damaged)!')
            if not record.asset_id.is_available:
                raise UserError('Aset ini sedang dipinjam oleh peminjaman lain!')
            record.state = 'borrowed'

    # BR-5: Action Return
    def action_return(self):
        for record in self:
            record.state = 'returned'
            record.return_date = fields.Date.context_today(self)

    # BR-6: Action Cancel
    def action_cancel(self):
        for record in self:
            record.state = 'cancelled'