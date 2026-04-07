import threading
import time

counter = 0


def test_global_counter():
    """
    A test that is prone to a race condition because it uses a global variable
    without synchronization.
    """
    global counter
    counter = 0

    def incr():
        global counter
        curr = counter
        time.sleep(0.01)  # Simulate some processing time
        counter = curr + 1

    threads = []
    for _ in range(5):
        t = threading.Thread(target=incr)
        t.start()
        threads.append(t)

    for t in threads:
        t.join()

    # This will often fail (expected counter is 5, but usually it will be less)
    assert counter == 5
