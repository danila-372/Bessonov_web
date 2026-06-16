document.addEventListener("DOMContentLoaded", () => {
    const dialog = document.querySelector("#delete-dialog");
    if (!dialog) {
        return;
    }

    const userName = dialog.querySelector("[data-delete-user-name]");
    const form = dialog.querySelector("form");

    document.querySelectorAll("[data-delete-button]").forEach((button) => {
        button.addEventListener("click", () => {
            userName.textContent = button.dataset.userName;
            form.action = button.dataset.deleteUrl;
            dialog.showModal();
        });
    });

    dialog.querySelector("[data-close-dialog]").addEventListener("click", () => {
        dialog.close();
    });
});
