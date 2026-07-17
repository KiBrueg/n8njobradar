"""
Seed demo B2B tenant: Demo Akademie + KI-Automatisierung course + search profile.
Idempotent (keyed by school name). Runs on VPS host via docker exec psql.
"""
import subprocess

SQL = """
DO $$
DECLARE
  v_school_id UUID;
  v_course_id UUID;
BEGIN
  SELECT id INTO v_school_id FROM schools WHERE name = 'Demo Akademie (Pilot)';
  IF v_school_id IS NULL THEN
    INSERT INTO schools (tenant_id, name, city, contact_email, plan, notes)
    VALUES (gen_random_uuid(), 'Demo Akademie (Pilot)', 'Berlin',
            'demo@jobradar.local', 'pilot',
            'Internal demo tenant — pitch material + pipeline E2E tests. Not a real client.')
    RETURNING id INTO v_school_id;
  END IF;

  SELECT id INTO v_course_id FROM courses
   WHERE school_id = v_school_id AND name = 'Weiterbildung KI-Automatisierung (n8n & Python)';
  IF v_course_id IS NULL THEN
    INSERT INTO courses (school_id, name, category, language_level, target_region, report_frequency)
    VALUES (v_school_id, 'Weiterbildung KI-Automatisierung (n8n & Python)',
            'automation', 'B2', 'Berlin / Remote DE', 'weekly')
    RETURNING id INTO v_course_id;
  END IF;

  IF NOT EXISTS (SELECT 1 FROM search_profiles WHERE course_id = v_course_id) THEN
    INSERT INTO search_profiles (
      course_id, name, target_titles, alternative_titles, exclude_titles,
      required_skills, nice_skills, seniority_filter, language_rules, location_rules,
      report_settings
    ) VALUES (
      v_course_id, 'Entry Automation',
      '["Automation Engineer", "AI Engineer", "n8n Developer", "Python Developer", "Junior Data Analyst"]',
      '["Workflow Automation", "Integration Engineer", "RPA Developer", "Werkstudent IT"]',
      '["Senior", "Lead", "Head of", "Principal", "Staff", "Manager", "Architekt"]',
      '["python", "n8n", "sql"]',
      '["docker", "fastapi", "api"]',
      ARRAY['junior', 'intern'],
      '{"accept": ["B1", "B2", "English"], "flag": ["C1"], "reject": []}',
      '{}',
      '{"top_n": 5}'
    );
  END IF;
END $$;
SELECT s.name, c.name, sp.name
FROM schools s
JOIN courses c ON c.school_id = s.id
JOIN search_profiles sp ON sp.course_id = c.id
WHERE s.name = 'Demo Akademie (Pilot)';
"""

r = subprocess.run(
    ["docker", "exec", "-i", "n8n-automation-postgres-1",
     "psql", "-U", "hub", "-d", "jobradar"],
    input=SQL, capture_output=True, text=True)
print(r.stdout or r.stderr)
