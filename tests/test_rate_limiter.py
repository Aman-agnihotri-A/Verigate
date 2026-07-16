from app.rate_limit import InMemoryTPSLimiter

def test_limiter_rejects_above_limit_within_one_second():
    limiter=InMemoryTPSLimiter()
    assert limiter.allow("alpha",2,now=10.0)
    assert limiter.allow("alpha",2,now=10.1)
    assert not limiter.allow("alpha",2,now=10.2)

def test_limiter_expires_old_events_and_is_per_client():
    limiter=InMemoryTPSLimiter()
    assert limiter.allow("alpha",1,now=10.0)
    assert limiter.allow("beta",1,now=10.1)
    assert limiter.allow("alpha",1,now=11.01)
