(function () {
    if (window.barquinaRealtime) {
        return;
    }

    function buildApi() {
        if (typeof window.io === "undefined") {
            return null;
        }
        const socket = window.io();
        const orderListeners = [];

        socket.on("order_updated", (payload) => {
            orderListeners.forEach((callback) => {
                try {
                    callback(payload);
                } catch (error) {
                    console.error("Realtime handler error", error);
                }
            });
        });

        socket.on("order_created", (payload) => {
            orderListeners.forEach((callback) => {
                try {
                    callback(payload);
                } catch (error) {
                    console.error("Realtime handler error", error);
                }
            });
        });

        return {
            socket,
            onOrderUpdate(callback) {
                if (typeof callback === "function") {
                    orderListeners.push(callback);
                }
            },
        };
    }

    window.barquinaRealtime = buildApi() || {
        onOrderUpdate() {
            /* noop when socket unavailable */
        },
    };
})();
