import threading
import time

from app.gpu import BigSlot


def test_hold_is_exclusive():
    slot, inside, peak, lock = BigSlot(), [0], [0], threading.Lock()

    def work(name):
        with slot.hold(name):
            with lock:
                inside[0] += 1
                peak[0] = max(peak[0], inside[0])
            time.sleep(0.05)
            with lock:
                inside[0] -= 1

    threads = [threading.Thread(target=work, args=(f"t{i}",)) for i in range(4)]
    for t in threads:
        t.start()
    for t in threads:
        t.join()
    assert peak[0] == 1


def test_ocr_yields_to_urgent():
    slot, events, ocr_in = BigSlot(), [], threading.Event()

    def ocr():
        with slot.hold("ocr"):
            events.append("ocr-in")
            ocr_in.set()
            while not slot.should_yield("ocr"):
                time.sleep(0.01)
            events.append("ocr-out")

    def planner():
        with slot.hold("planner", urgent=True):
            events.append("planner-in")

    a = threading.Thread(target=ocr)
    a.start()
    ocr_in.wait(1)
    t0 = time.perf_counter()
    b = threading.Thread(target=planner)
    b.start()
    b.join(2)
    a.join(2)
    assert events == ["ocr-in", "ocr-out", "planner-in"]
    assert time.perf_counter() - t0 < 1


def test_urgent_waiter_goes_before_normal_waiter():
    slot, order, holding = BigSlot(), [], threading.Event()
    release = threading.Event()

    def holder():
        with slot.hold("first"):
            holding.set()
            release.wait(2)

    def waiter(name, urgent):
        with slot.hold(name, urgent=urgent):
            order.append(name)

    h = threading.Thread(target=holder)
    h.start()
    holding.wait(1)
    normal = threading.Thread(target=waiter, args=("normal", False))
    normal.start()
    time.sleep(0.05)
    urgent = threading.Thread(target=waiter, args=("urgent", True))
    urgent.start()
    time.sleep(0.05)
    release.set()
    for t in (h, normal, urgent):
        t.join(2)
    assert order == ["urgent", "normal"]
