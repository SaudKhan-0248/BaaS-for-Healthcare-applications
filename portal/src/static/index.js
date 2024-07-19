const sideMenu = document.querySelector("aside");
const menuBtn = document.querySelector("#menu-btn");
const closeBtn = document.querySelector("#close-btn");
const themeToggler = document.querySelector(".theme-toggler");

//show Sidebar
menuBtn.addEventListener("click", () => {
  sideMenu.style.display = "block";
});

//close Sidebar
closeBtn.addEventListener("click", () => {
  sideMenu.style.display = "none";
});

//change Theme
themeToggler.addEventListener("click", () => {
  document.body.classList.toggle("dark-theme-variables");
  themeToggler.querySelector("span:nth-child(1)").classList.toggle("active");
  themeToggler.querySelector("span:nth-child(2)").classList.toggle("active");
});


document.addEventListener("DOMContentLoaded", function () {
  initializeDashboard();
});


document.body.addEventListener('htmx:afterSwap', function(event) {
  if (event.detail.target.id === "main") {
    initializeDashboard();
  }
});

function initializeDashboard() {
  updateCards();
  updateCircles();
}

function updateCircles() {
  const numberElements = document.querySelectorAll(".number p");
  numberElements.forEach((numberElement) => {
    const percentage = parseFloat(numberElement.textContent);
    const circleElement = numberElement
      .closest(".performance")
      .querySelector("circle");
    const circumference = 2 * Math.PI * circleElement.getAttribute("r");
    const progress = circumference * (percentage / 100);
    circleElement.style.strokeDasharray = `${progress} ${circumference}`;
  });
}

let eventSourceInitialized = false;
let eventSource

function updateCards() {
  const total_req = document.getElementById("total-req");
  const success_resp = document.getElementById("success-resp");
  const error_resp = document.getElementById("error-resp");

  if (!eventSourceInitialized) {
    eventSource = new EventSource("http://localhost:8000/stream/6651862de66ba56c4dd11a9d");
  }

  eventSource.onmessage = function(e) {
    console.log("got into on message")
    try {
      const data = JSON.parse(e.data);
      total_req.innerHTML = data.total_req;
      success_resp.innerHTML = data.success_resp;
      error_resp.innerHTML = data.error_resp;
    } catch (error) {
      console.error("Error parsing JSON:", error);
    }
  };

  eventSource.onerror = function(error) {
    console.error("EventSource error:", error);
  };

  eventSourceInitialized = true;
}
