import pytest

from timeutil import get_time_to_sleep


@pytest.mark.parametrize(
    "cur_hr,cur_min,start_hr,end_hr,exp_val",
    [
        (22, 20, 7, 22, 31200),
        (22, 0, 7, 22, 32400),
        (6, 30, 7, 22, 1800),
        (0, 0, 7, 22, 25200),
        (0, 10, 7, 22, 24600),
        (23, 10, 0, 2, 3000),
        (16, 30, 0, 2, 27000),
    ],
)
def test_get_time_sleep(cur_hr, cur_min, start_hr, end_hr, exp_val):
    """
    Test outcomes of the time to sleep computation.
    """
    assert get_time_to_sleep(cur_hr, cur_min, start_hr, end_hr) == exp_val


@pytest.mark.parametrize(
    "cur_hr,start_hr,end_hr", [(7, 7, 22), (13, 7, 14), (8, 10, 7)]
)
def test_get_time_sleep_neg(cur_hr, start_hr, end_hr):
    """
    Ensure time to sleep computation refuses invalid inputs.
    """
    with pytest.raises(AssertionError):
        get_time_to_sleep(cur_hr, 0, start_hr, end_hr)
