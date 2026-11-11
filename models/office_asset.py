from odoo import models, fields, api


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
