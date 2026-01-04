// failcore/web/static/js/cost_chart.js
/**
 * Cost Chart - Chart.js implementation for cost tracking
 * 
 * Renders cost curve with:
 * - Cumulative cost line
 * - Budget threshold line
 * - Blocked event markers
 */

/**
 * Initialize cost chart for a run
 * @param {string} runId - Run ID
 * @param {HTMLCanvasElement} canvas - Canvas element for chart
 */
function initCostChart(runId, canvas) {
    if (!runId || !canvas) {
        console.error('Cost chart: missing runId or canvas');
        return;
    }
    
    // Load cost data
    fetch(`/api/runs/${encodeURIComponent(runId)}/cost`)
        .then(response => {
            if (!response.ok) {
                throw new Error(`HTTP ${response.status}`);
            }
            return response.json();
        })
        .then(data => {
            renderCostChart(canvas, data);
        })
        .catch(error => {
            console.error('Error loading cost data:', error);
            // Show error message
            const container = canvas.parentElement;
            if (container) {
                container.innerHTML = `<div class="cost-error">Error loading cost data: ${error.message}</div>`;
            }
        });
}

/**
 * Render cost chart using Chart.js
 * @param {HTMLCanvasElement} canvas - Canvas element
 * @param {Object} data - Cost data { points, budget, events }
 */
function renderCostChart(canvas, data) {
    const { points, budget, events } = data;
    
    if (!points || points.length === 0) {
        canvas.parentElement.innerHTML = '<div class="cost-loading">No cost data available</div>';
        return;
    }
    
    // Prepare chart data
    const labels = points.map((p, idx) => `Step ${p.seq}`);
    const cumulativeCostData = points.map(p => p.cum_cost_usd);
    
    // Find max cost for scaling
    const maxCost = Math.max(...cumulativeCostData, budget.max_cost_usd || 0, 0.01);
    
    // Create datasets
    const datasets = [
        {
            label: 'Cumulative Cost',
            data: cumulativeCostData,
            borderColor: 'rgb(75, 192, 192)',
            backgroundColor: 'rgba(75, 192, 192, 0.1)',
            borderWidth: 2,
            fill: true,
            stepped: 'after',  // Step chart
            tension: 0,
        }
    ];
    
    // Add budget threshold line
    if (budget.max_cost_usd) {
        datasets.push({
            label: 'Budget Limit',
            data: Array(points.length).fill(budget.max_cost_usd),
            borderColor: 'rgb(255, 99, 132)',
            backgroundColor: 'rgba(255, 99, 132, 0.1)',
            borderWidth: 2,
            borderDash: [5, 5],
            fill: false,
            pointRadius: 0,
        });
    }
    
    // Create chart configuration
    const config = {
        type: 'line',
        data: {
            labels: labels,
            datasets: datasets,
        },
        options: {
            responsive: true,
            maintainAspectRatio: false,
            interaction: {
                intersect: false,
                mode: 'index',
            },
            plugins: {
                legend: {
                    display: true,
                    position: 'top',
                },
                tooltip: {
                    callbacks: {
                        label: function(context) {
                            const datasetLabel = context.dataset.label || '';
                            const value = context.parsed.y;
                            if (datasetLabel === 'Cumulative Cost') {
                                const point = points[context.dataIndex];
                                return [
                                    `${datasetLabel}: $${value.toFixed(6)}`,
                                    `Delta: $${point.delta_cost_usd.toFixed(6)}`,
                                    `Tokens: ${point.cum_tokens.toLocaleString()}`,
                                    `Tool: ${point.tool}`,
                                ];
                            } else {
                                return `${datasetLabel}: $${value.toFixed(2)}`;
                            }
                        }
                    }
                }
            },
            scales: {
                y: {
                    beginAtZero: true,
                    title: {
                        display: true,
                        text: 'Cost (USD)'
                    },
                    ticks: {
                        callback: function(value) {
                            return '$' + value.toFixed(4);
                        }
                    }
                },
                x: {
                    title: {
                        display: true,
                        text: 'Step'
                    }
                }
            },
            // Add annotations for blocked events
            onHover: (event, activeElements) => {
                canvas.style.cursor = activeElements.length > 0 ? 'pointer' : 'default';
            },
            onClick: (event, activeElements) => {
                if (activeElements.length > 0) {
                    const index = activeElements[0].index;
                    const point = points[index];
                    if (point.status === 'BLOCKED' || point.status === 'blocked') {
                        // Show blocked event details
                        alert(`Step ${point.seq} blocked\nTool: ${point.tool}\nError: ${point.error_code || 'Unknown'}`);
                    }
                }
            }
        }
    };
    
    // Create chart
    const chart = new Chart(canvas, config);
    
    // Add blocked event markers after chart is rendered
    chart.update();
    
    if (events && events.length > 0) {
        // Use Chart.js plugin to draw blocked event markers
        chart.options.plugins.annotation = chart.options.plugins.annotation || {};
        
        // Mark blocked points with custom styling
        chart.data.datasets[0].pointRadius = points.map((p, idx) => {
            const isBlocked = events.some(e => e.seq === p.seq);
            return isBlocked ? 8 : 3;
        });
        chart.data.datasets[0].pointBackgroundColor = points.map((p, idx) => {
            const isBlocked = events.some(e => e.seq === p.seq);
            return isBlocked ? 'rgb(255, 0, 0)' : 'rgb(75, 192, 192)';
        });
        chart.data.datasets[0].pointBorderColor = points.map((p, idx) => {
            const isBlocked = events.some(e => e.seq === p.seq);
            return isBlocked ? 'rgb(255, 255, 255)' : 'rgb(75, 192, 192)';
        });
        chart.data.datasets[0].pointBorderWidth = points.map((p, idx) => {
            const isBlocked = events.some(e => e.seq === p.seq);
            return isBlocked ? 2 : 1;
        });
        
        chart.update();
    }
}

// Auto-initialize if canvas exists
document.addEventListener('DOMContentLoaded', function() {
    const canvas = document.getElementById('cost-chart-canvas');
    if (canvas) {
        const runDetailPage = document.querySelector('.run-detail-page');
        const runId = runDetailPage?.dataset?.runId;
        if (runId) {
            initCostChart(runId, canvas);
        }
    }
});
