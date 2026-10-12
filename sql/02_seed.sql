-- Deterministic fictitious seed data: 20 students, 60 access log rows.
-- Names, documents and emails are invented.

INSERT INTO school.students
    (student_id, document_number, full_name, email, program, enrollment_date, status)
VALUES
    (1,  'DOC-100001', 'Laura Gomez',      'laura.gomez@example.edu',      'Software Engineering', '2023-02-01', 'active'),
    (2,  'DOC-100002', 'Andres Ruiz',      'andres.ruiz@example.edu',      'Data Science',         '2023-02-01', 'active'),
    (3,  'DOC-100003', 'Camila Torres',    'camila.torres@example.edu',    'Industrial Design',    '2022-08-01', 'graduated'),
    (4,  'DOC-100004', 'Mateo Vargas',     'mateo.vargas@example.edu',     'Software Engineering', '2024-02-01', 'active'),
    (5,  'DOC-100005', 'Valentina Rios',   'valentina.rios@example.edu',   'Accounting',           '2021-08-01', 'graduated'),
    (6,  'DOC-100006', 'Santiago Mejia',   'santiago.mejia@example.edu',   'Data Science',         '2024-08-01', 'active'),
    (7,  'DOC-100007', 'Isabella Castro',  'isabella.castro@example.edu',  'Psychology',           '2023-08-01', 'inactive'),
    (8,  'DOC-100008', 'Samuel Herrera',   'samuel.herrera@example.edu',   'Civil Engineering',    '2022-02-01', 'active'),
    (9,  'DOC-100009', 'Mariana Ospina',   'mariana.ospina@example.edu',   'Software Engineering', '2024-02-01', 'active'),
    (10, 'DOC-100010', 'Nicolas Restrepo', 'nicolas.restrepo@example.edu', 'Accounting',           '2023-02-01', 'active'),
    (11, 'DOC-100011', 'Sofia Cardenas',   'sofia.cardenas@example.edu',   'Psychology',           '2022-08-01', 'active'),
    (12, 'DOC-100012', 'Juan Pablo Lopez', 'juanpablo.lopez@example.edu',  'Data Science',         '2025-02-01', 'active'),
    (13, 'DOC-100013', 'Daniela Arango',   'daniela.arango@example.edu',   'Industrial Design',    '2024-08-01', 'active'),
    (14, 'DOC-100014', 'Tomas Zapata',     'tomas.zapata@example.edu',     'Civil Engineering',    '2021-02-01', 'graduated'),
    (15, 'DOC-100015', 'Gabriela Munoz',   'gabriela.munoz@example.edu',   'Software Engineering', '2025-08-01', 'active'),
    (16, 'DOC-100016', 'Felipe Salazar',   'felipe.salazar@example.edu',   'Accounting',           '2023-08-01', 'inactive'),
    (17, 'DOC-100017', 'Antonia Velez',    'antonia.velez@example.edu',    'Psychology',           '2025-02-01', 'active'),
    (18, 'DOC-100018', 'Emilio Franco',    'emilio.franco@example.edu',    'Data Science',         '2022-02-01', 'active'),
    (19, 'DOC-100019', 'Lucia Montoya',    'lucia.montoya@example.edu',    'Civil Engineering',    '2024-02-01', 'active'),
    (20, 'DOC-100020', 'Martin Giraldo',   'martin.giraldo@example.edu',   'Industrial Design',    '2025-08-01', 'active');

-- Three access events per student, spread over 2026-09-01..03.
-- Inactive students are denied; everyone else succeeds.
INSERT INTO school.access_logs (student_id, accessed_at, resource, result, ip_address)
SELECT
    s.student_id,
    TIMESTAMP '2026-09-01 07:00' + (n - 1) * INTERVAL '1 day' + s.student_id * INTERVAL '7 minutes',
    (ARRAY['campus_portal', 'library', 'virtual_classroom'])[n],
    CASE WHEN s.status = 'inactive' THEN 'denied' ELSE 'success' END,
    ('10.20.' || n || '.' || s.student_id)::INET
FROM school.students AS s
CROSS JOIN generate_series(1, 3) AS n
ORDER BY n, s.student_id;
