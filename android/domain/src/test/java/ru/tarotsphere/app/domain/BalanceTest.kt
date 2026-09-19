package ru.tarotsphere.app.domain

import org.junit.Assert.*
import org.junit.Test
import ru.tarotsphere.app.domain.model.Balance

class BalanceTest {
    @Test fun expiredOrMalformedSubscriptionDoesNotGrantAccess() {
        assertFalse(Balance(0, 0, "2000-01-01T00:00:00", 0).canDivinate)
        assertFalse(Balance(0, 0, "not a date", 0).canDivinate)
        assertFalse(Balance(0, 0, null, 0).canDivinate)
    }
    @Test fun freePaidAndActiveSubscriptionGrantAccess() {
        assertTrue(Balance(1, 0, null, 0).canDivinate)
        assertTrue(Balance(0, 1, null, 0).canDivinate)
        assertTrue(Balance(0, 0, "2999-01-01T00:00:00+03:00", 0).canDivinate)
    }
}
