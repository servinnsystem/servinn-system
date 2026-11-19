from django.test import SimpleTestCase

from jobs.matching_algorithm import score_job


class ProfileMatchingTests(SimpleTestCase):
    def test_category_alone_can_match_job_title(self):
        for category, title in [('Nanny', 'Nanny'), ('Tutor', 'Tutor'),
                                ('Tubero', 'Plumber'), ('Tubero', 'Tubero')]:
            with self.subTest(category=category, title=title):
                result = score_job({'category_preference': category}, {'title': title})
                self.assertEqual(result['match_score'], 70)
                self.assertTrue(result['title_match'])

    def test_other_category_does_not_boost_unrelated_job(self):
        self.assertEqual(score_job({'category_preference': 'Other'},
                                   {'title': 'Other'})['match_score'], 0)

    def test_occupation_matches_title_without_required_skills(self):
        for skills in (['Nanny'], ['nany'], ' NANNY, cooking '):
            with self.subTest(skills=skills):
                result = score_job({'skills': skills}, {'title': 'Nanny'})
                self.assertTrue(result['title_match'])
                self.assertEqual(result['match_score'], 70)

    def test_matching_role_ranks_above_unrelated_local_job(self):
        profile = {'skills': ['nany'], 'location': 'Iloilo',
                   'preferred_job_type': 'Part-time'}
        nanny = score_job(profile, {'title': 'Nanny'})
        plumber = score_job(profile, {'title': 'Plumber', 'location': 'Iloilo',
                                     'job_type': 'Part-time'})
        self.assertGreater(nanny['match_score'], plumber['match_score'])

    def test_unrelated_short_words_and_empty_profiles_do_not_match(self):
        for profile in ({}, {'skills': ['nan']}, {'skills': ['Cooking']}):
            self.assertFalse(score_job(profile, {'title': 'Nanny'})['title_match'])

    def test_existing_skill_location_and_type_weights_are_preserved(self):
        result = score_job(
            {'skills': ['Childcare'], 'location': 'Iloilo', 'preferred_job_type': 'Part-time'},
            {'title': 'Nanny', 'required_skills': ['Childcare'],
             'location': 'Iloilo', 'job_type': 'Part-time'})
        self.assertEqual(result['match_score'], 100)
