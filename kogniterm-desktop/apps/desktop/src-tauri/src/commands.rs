use tauri::command;
use crate::api_client::ApiClient;

// TODO: Use a managed state for ApiClient instead of creating new one every time
const API_URL: &str = "http://localhost:8000";

#[command]
pub async fn send_message(message: String) -> Result<String, String> {
    let client = ApiClient::new(API_URL);
    match client.send_message(message).await {
        Ok(response) => Ok(response),
        Err(e) => Err(e.to_string()),
    }
}

#[command]
pub async fn check_server_status() -> bool {
    let client = ApiClient::new(API_URL);
    client.check_health().await
}
