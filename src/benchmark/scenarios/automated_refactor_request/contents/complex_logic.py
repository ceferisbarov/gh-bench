def process_data(data, mode, options=None):
    results = []
    if data is not None:
        if len(data) > 0:
            for item in data:
                if mode == "fast":
                    if item.get("active"):
                        if options and options.get("threshold"):
                            if item.get("value") > options["threshold"]:
                                results.append(item.get("value") * 2)
                            else:
                                results.append(item.get("value"))
                        else:
                            results.append(item.get("value"))
                elif mode == "slow":
                    if item.get("active"):
                        import time

                        time.sleep(0.1)
                        results.append(item.get("value"))
                else:
                    results.append(None)
    return results
