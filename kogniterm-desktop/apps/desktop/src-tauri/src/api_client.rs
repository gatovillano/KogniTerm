use serde::{Deserialize, Serialize};
use reqwest::Client;
use std::error::Error;

#[derive(Debug, Serialize, Deserialize)]
pub struct ChatRequest {
    pub message: String,
}

#[derive(Debug, Serialize, Deserialize)]
pub struct ChatResponse {
    pub response: String,
}

pub struct ApiClient {
    client: Client,
    base_url: String,
}

impl ApiClient {
    pub fn new(base_url: &str) -> Self {
        Self {
            client: Client::new(),
            base_url: base_url.to_string(),
        }
    }

    pub async fn send_message(&self, message: String) -> Result<String, Box<dyn Error>> {
        let url = format!("{}/api/chat", self.base_url);
        let payload = ChatRequest { message };

        let resp = self.client.post(&url)
            .json(&payload)
            .send()
            .await?
            .json::<ChatResponse>()
            .await?;

        Ok(resp.response)
    }

    pub async fn check_health(&self) -> bool {
        let url = format!("{}/api/health", self.base_url);
        match self.client.get(&url).send().await {
            Ok(resp) => resp.status().is_success(),
            Err(_) => false,
        }
    }
}
