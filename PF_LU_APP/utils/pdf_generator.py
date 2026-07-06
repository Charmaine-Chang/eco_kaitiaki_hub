from datetime import datetime

try:
    from fpdf import FPDF
    FPDF_AVAILABLE = True
except ImportError:
    FPDF_AVAILABLE = False
    FPDF = object  # Dummy to prevent NameError if not installed

REPORT_LABELS = {
    'summary': 'Executive Summary',
    'species': 'Species Analysis',
    'full': 'Full Data Report',
}

if FPDF_AVAILABLE:
    class ExportPDF(FPDF):
        def __init__(self, group_name, title, filter_summary):
            super().__init__()
            self.group_name = group_name
            self.title_text = title
            self.filter_summary = filter_summary
            self.generated_date = datetime.now().strftime('%d/%m/%Y %H:%M')

        def header(self):
            self.set_fill_color(26, 94, 32)
            self.rect(0, 0, 210, 8, 'F')
            self.ln(5)
            self.set_font('helvetica', 'B', 15)
            self.set_text_color(26, 94, 32)
            self.cell(0, 10, self.group_name.encode('latin-1', 'replace').decode('latin-1'), ln=True)
            self.set_font('helvetica', 'B', 11)
            self.set_text_color(100, 100, 100)
            self.cell(0, 6, self.title_text.encode('latin-1', 'replace').decode('latin-1'), ln=True)
            self.set_font('helvetica', '', 9)
            self.set_text_color(120, 120, 120)
            self.cell(0, 5, f"Generated: {self.generated_date} | Filters: {self.filter_summary}".encode('latin-1', 'replace').decode('latin-1'), ln=True)
            self.set_draw_color(200, 200, 200)
            self.line(10, self.get_y() + 2, 200, self.get_y() + 2)
            self.ln(8)

        def footer(self):
            self.set_y(-15)
            self.set_font('helvetica', 'I', 8)
            self.set_text_color(150, 150, 150)
            self.cell(0, 10, f"Page {self.page_no()}/{{nb}} | Eco Kaitiaki Hub - Predator Control".encode('latin-1', 'replace').decode('latin-1'), align='C')

    def generate_graphs_report_pdf(group_name, species_data, lines_data, dates_data,
                                    kpis, recent_catches, report_type, filter_summary):
        pdf = ExportPDF(group_name, REPORT_LABELS.get(report_type, 'Report'), filter_summary)
        pdf.alias_nb_pages()
        pdf.add_page()

        pdf.set_font('helvetica', 'B', 12)
        pdf.set_text_color(26, 94, 32)
        pdf.cell(0, 8, 'Key Performance Indicators'.encode('latin-1', 'replace').decode('latin-1'), ln=True)
        pdf.ln(2)

        kpi_items = [
            ('Total Catches', str(kpis.get('total_catches', 0))),
            ('Active Lines', str(kpis.get('active_lines', 0))),
            ('Success Rate', f"{kpis.get('success_rate', 0)}%"),
            ('Top Hotspot', kpis.get('hotspot', 'N/A')),
        ]
        pdf.set_font('helvetica', '', 9)
        pdf.set_text_color(50, 50, 50)
        pdf.set_fill_color(245, 248, 245)
        col_w = 190 / 4
        for i, (label, val) in enumerate(kpi_items):
            fill = i % 2 == 0
            pdf.cell(col_w, 12, f"{label}: {val}".encode('latin-1', 'replace').decode('latin-1'),
                     border=1, align='C', fill=fill)
        pdf.ln(16)

        if report_type in ('summary', 'species', 'full') and species_data:
            pdf.set_font('helvetica', 'B', 12)
            pdf.set_text_color(26, 94, 32)
            pdf.cell(0, 8, 'Species Distribution'.encode('latin-1', 'replace').decode('latin-1'), ln=True)
            pdf.ln(2)
            pdf.set_font('helvetica', 'B', 9)
            pdf.set_fill_color(26, 94, 32)
            pdf.set_text_color(255, 255, 255)
            pdf.cell(130, 7, 'Species'.encode('latin-1', 'replace').decode('latin-1'), border=1, fill=True)
            pdf.cell(60, 7, 'Count'.encode('latin-1', 'replace').decode('latin-1'), border=1, align='C', fill=True)
            pdf.ln()
            pdf.set_font('helvetica', '', 9)
            pdf.set_text_color(50, 50, 50)
            fill = False
            for row in species_data:
                name = (row.get('species_name') or 'Unknown').encode('latin-1', 'replace').decode('latin-1')
                count = str(row.get('count', 0))
                pdf.set_fill_color(245, 248, 245) if fill else pdf.set_fill_color(255, 255, 255)
                pdf.cell(130, 6, name, border=1, fill=True)
                pdf.cell(60, 6, count, border=1, align='C', fill=True)
                pdf.ln()
                fill = not fill
            pdf.ln(6)

        if report_type in ('summary', 'full') and lines_data:
            pdf.set_font('helvetica', 'B', 12)
            pdf.set_text_color(26, 94, 32)
            pdf.cell(0, 8, 'Line Performance'.encode('latin-1', 'replace').decode('latin-1'), ln=True)
            pdf.ln(2)
            pdf.set_font('helvetica', 'B', 9)
            pdf.set_fill_color(26, 94, 32)
            pdf.set_text_color(255, 255, 255)
            pdf.cell(130, 7, 'Line'.encode('latin-1', 'replace').decode('latin-1'), border=1, fill=True)
            pdf.cell(60, 7, 'Catches'.encode('latin-1', 'replace').decode('latin-1'), border=1, align='C', fill=True)
            pdf.ln()
            pdf.set_font('helvetica', '', 9)
            pdf.set_text_color(50, 50, 50)
            fill = False
            for row in lines_data:
                name = (row.get('line_name') or 'Unknown').encode('latin-1', 'replace').decode('latin-1')
                count = str(row.get('count', 0))
                pdf.set_fill_color(245, 248, 245) if fill else pdf.set_fill_color(255, 255, 255)
                pdf.cell(130, 6, name, border=1, fill=True)
                pdf.cell(60, 6, count, border=1, align='C', fill=True)
                pdf.ln()
                fill = not fill
            pdf.ln(6)

        if report_type in ('species', 'full') and dates_data:
            pdf.set_font('helvetica', 'B', 12)
            pdf.set_text_color(26, 94, 32)
            pdf.cell(0, 8, 'Catch Trends'.encode('latin-1', 'replace').decode('latin-1'), ln=True)
            pdf.ln(2)
            pdf.set_font('helvetica', 'B', 9)
            pdf.set_fill_color(26, 94, 32)
            pdf.set_text_color(255, 255, 255)
            pdf.cell(100, 7, 'Date'.encode('latin-1', 'replace').decode('latin-1'), border=1, fill=True)
            pdf.cell(90, 7, 'Catches'.encode('latin-1', 'replace').decode('latin-1'), border=1, align='C', fill=True)
            pdf.ln()
            pdf.set_font('helvetica', '', 9)
            pdf.set_text_color(50, 50, 50)
            fill = False
            for row in dates_data:
                d = (row.get('catch_date') or '--').encode('latin-1', 'replace').decode('latin-1')
                c = str(row.get('count', 0))
                pdf.set_fill_color(245, 248, 245) if fill else pdf.set_fill_color(255, 255, 255)
                pdf.cell(100, 6, d, border=1, fill=True)
                pdf.cell(90, 6, c, border=1, align='C', fill=True)
                pdf.ln()
                fill = not fill
            pdf.ln(6)

        if report_type == 'full' and recent_catches:
            if pdf.get_y() > 200:
                pdf.add_page()
            pdf.set_font('helvetica', 'B', 12)
            pdf.set_text_color(26, 94, 32)
            pdf.cell(0, 8, 'Recent Catches (Last 10)'.encode('latin-1', 'replace').decode('latin-1'), ln=True)
            pdf.ln(2)
            pdf.set_font('helvetica', 'B', 8)
            pdf.set_fill_color(26, 94, 32)
            pdf.set_text_color(255, 255, 255)
            pdf.cell(30, 7, 'Date'.encode('latin-1', 'replace').decode('latin-1'), border=1, fill=True)
            pdf.cell(40, 7, 'Species'.encode('latin-1', 'replace').decode('latin-1'), border=1, fill=True)
            pdf.cell(30, 7, 'Trap'.encode('latin-1', 'replace').decode('latin-1'), border=1, fill=True)
            pdf.cell(50, 7, 'Line'.encode('latin-1', 'replace').decode('latin-1'), border=1, fill=True)
            pdf.cell(40, 7, 'Group'.encode('latin-1', 'replace').decode('latin-1'), border=1, fill=True)
            pdf.ln()
            pdf.set_font('helvetica', '', 8)
            pdf.set_text_color(50, 50, 50)
            fill = False
            for rc in recent_catches:
                d = (rc['date'].strftime('%d %b %H:%M') if rc.get('date') else '--').encode('latin-1', 'replace').decode('latin-1')
                sp = (rc.get('species_name') or '--').encode('latin-1', 'replace').decode('latin-1')
                tc = (f"#{rc.get('trap_code', '?')}").encode('latin-1', 'replace').decode('latin-1')
                ln = (rc.get('line_name') or '--').encode('latin-1', 'replace').decode('latin-1')
                gr = (rc.get('group_name') or '--').encode('latin-1', 'replace').decode('latin-1')
                pdf.set_fill_color(245, 248, 245) if fill else pdf.set_fill_color(255, 255, 255)
                pdf.cell(30, 6, d, border=1, fill=True)
                pdf.cell(40, 6, sp, border=1, fill=True)
                pdf.cell(30, 6, tc, border=1, fill=True)
                pdf.cell(50, 6, ln, border=1, fill=True)
                pdf.cell(40, 6, gr, border=1, fill=True)
                pdf.ln()
                fill = not fill

        pdf_data = pdf.output()
        if isinstance(pdf_data, str):
            pdf_data = pdf_data.encode('latin1')
        elif isinstance(pdf_data, bytearray):
            pdf_data = bytes(pdf_data)
        return pdf_data

    def generate_table_export_pdf(group_name, title, filter_summary, active_cols, field_map, rows, column_weights):
        total_width = 190
        selected_weights = [column_weights.get(c, 25) for c in active_cols]
        sum_weights = sum(selected_weights)
        
        col_widths = [int(w * total_width / sum_weights) for w in selected_weights]
        diff = total_width - sum(col_widths)
        if col_widths:
            col_widths[-1] += diff

        pdf = ExportPDF(group_name, title, filter_summary)
        pdf.alias_nb_pages()
        pdf.add_page()

        pdf.set_font('helvetica', 'B', 9)
        pdf.set_fill_color(26, 94, 32)
        pdf.set_text_color(255, 255, 255)
        for i, col_key in enumerate(active_cols):
            header_label = field_map[col_key][1]
            pdf.cell(col_widths[i], 7, header_label.encode('latin-1', 'replace').decode('latin-1'), border=1, align='L', fill=True)
        pdf.ln()

        pdf.set_font('helvetica', '', 8)
        pdf.set_text_color(50, 50, 50)
        fill = False
        
        if not rows:
            pdf.set_font('helvetica', 'I', 10)
            pdf.cell(0, 10, "No records found matching the criteria.".encode('latin-1', 'replace').decode('latin-1'), ln=True)
        else:
            for row in rows:
                pdf.set_fill_color(245, 248, 245) if fill else pdf.set_fill_color(255, 255, 255)
                for i, col_key in enumerate(active_cols):
                    col_field_name = field_map[col_key][0]
                    val = str(row[col_field_name] or '')
                    char_limit = int(col_widths[i] * 1.5)
                    if len(val) > char_limit:
                        val = val[:char_limit-3] + "..."
                    pdf.cell(col_widths[i], 6, val.encode('latin-1', 'replace').decode('latin-1'), border=1, align='L', fill=True)
                pdf.ln()
                fill = not fill

        pdf_data = pdf.output()
        if isinstance(pdf_data, str):
            pdf_data = pdf_data.encode('latin1')
        elif isinstance(pdf_data, bytearray):
            pdf_data = bytes(pdf_data)
        return pdf_data

else:
    def generate_graphs_report_pdf(*args, **kwargs):
        raise RuntimeError("PDF generation requires 'fpdf2' package. Install with: pip install fpdf2")
    def generate_table_export_pdf(*args, **kwargs):
        raise RuntimeError("PDF generation requires 'fpdf2' package. Install with: pip install fpdf2")
