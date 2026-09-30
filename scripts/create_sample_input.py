import openpyxl

wb = openpyxl.Workbook()
ws = wb.active
ws.append(["Entity Name", "Entity Type"])
rows = [
    ("Bajaj Finance Limited", "NBFC"),
    ("HDFC ERGO General Insurance Company Limited", "Insurer"),
    ("Apollo Hospitals Enterprise Limited", "Hospital"),
    ("Dr. Reddy's Laboratories Limited", "Pharma"),
    ("Manappuram Finance Limited", "NBFC"),
    ("ICICI Lombard General Insurance Company Limited", "Insurer"),
    ("Max Healthcare Institute Limited", "Hospital"),
    ("Cipla Limited", "Pharma"),
]
for r in rows:
    ws.append(r)
ws.column_dimensions["A"].width = 48
ws.column_dimensions["B"].width = 14
wb.save("sample_bfsi_healthcare_entities.xlsx")
print("created sample_bfsi_healthcare_entities.xlsx")
