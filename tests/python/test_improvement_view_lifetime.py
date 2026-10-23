"""Retained host reconstruction may replace only fully closed concrete lifetimes."""
from _paths import ROOT, SERVER  # noqa: F401

import asyncio
import unittest
from unittest.mock import patch

import improvement_store as IM
from improvement_claude import ClaudeTrialAdapter
from improvement_experiment_service import ExperimentService
from improvement_trial_service import OwnerTrialService
from improvement_views import EffectiveViews
import test_improvement_view_next as next_fixtures
import test_improvement_view_sources as sources


class ViewLifetimeTests(sources.SourceFixture, unittest.IsolatedAsyncioTestCase):
    owned_service = next_fixtures.ViewNextTests.owned_service
    admit = next_fixtures.ViewNextTests.admit

    def rebuild(self):
        owner_service = OwnerTrialService(self.host)
        self.addAsyncCleanup(owner_service.close)
        service = ExperimentService(self.f.plans, owner_service)
        self.addAsyncCleanup(service.close)
        return service

    async def test_rebuilt_owner_can_use_frozen_views_after_both_prior_lifetimes_close(self):
        old, metadata = self.owned_service()
        previous = old.views
        await old.close()
        await old.trial_service.close()
        rebuilt = self.rebuild()
        with patch.object(ClaudeTrialAdapter, 'verify', return_value={'supported': True, 'capability_hash': 'c' * 64}):
            admitted = self.admit(rebuilt, key='view-lifetime-rebuilt-current-admission')
        self.assertEqual(admitted.request['view']['binding_hash'], metadata['binding_hash'])
        self.assertIsNot(rebuilt.views, previous)
        self.assertIs(rebuilt.views.semantic, rebuilt.semantic)
        self.assertIs(rebuilt.trials._views, rebuilt.views)
        self.assertIs(self.host._views, rebuilt.views)

    async def test_closed_role_with_live_owner_cannot_replace_its_bound_resolver(self):
        old, _ = self.owned_service()
        await old.close()
        self.assertFalse(old.trial_service._closed)
        rebuilt = self.rebuild()
        fresh = EffectiveViews(self.f.plans, rebuilt.semantic)
        self.assertIs(rebuilt.views, old.views)
        with self.assertRaisesRegex(IM.ConflictError, 'already_bound'):
            self.host.bind_views(fresh)
        with self.assertRaisesRegex(IM.ConflictError, 'already_bound'):
            self.f.plans.admission.trials.bind_views(fresh)

    async def test_missing_pending_cancelled_or_failed_owner_close_never_allows_rebinding(self):
        old, _ = self.owned_service()
        await old.close()
        await old.trial_service.close()
        owner, complete = old.trial_service, old.trial_service._closing
        pending = asyncio.get_running_loop().create_future()
        cancelled = asyncio.get_running_loop().create_future()
        cancelled.cancel()
        failed = asyncio.get_running_loop().create_future()
        failed.set_exception(RuntimeError('Synthetic incomplete cleanup; never a successful close'))
        try:
            for closing in (None, pending, cancelled, failed):
                with self.subTest(closing=closing):
                    owner._closing = closing
                    rebuilt = self.rebuild()
                    self.assertIs(rebuilt.views, old.views)
                    fresh = EffectiveViews(self.f.plans, rebuilt.semantic)
                    with self.assertRaisesRegex(IM.ConflictError, 'already_bound'):
                        self.host.bind_views(fresh)
                    with self.assertRaisesRegex(IM.ConflictError, 'already_bound'):
                        self.f.plans.admission.trials.bind_views(fresh)
        finally:
            owner._closing = complete
            pending.cancel()
            failed.exception()


if __name__ == '__main__':
    unittest.main()
